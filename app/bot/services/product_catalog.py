import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from app.config import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)

DEFAULT_PRODUCTS_PATH = DEFAULT_DATA_DIR / "products.json"
DEFAULT_OPERATORS_PATH = DEFAULT_DATA_DIR / "operators.json"
DEFAULT_VPN_PROFILES_PATH = DEFAULT_DATA_DIR / "vpn_profiles.json"


@dataclass
class VpnProfile:
    slug: str
    name: str
    emoji: str
    inbound_remark: str
    order: int
    client_flow: str = ""
    locations: list[str] = field(default_factory=list)
    kind: str = "universal"
    legacy_slugs: list[str] = field(default_factory=list)


Operator = VpnProfile


@dataclass
class Product:
    slug: str
    name: str
    emoji: str
    description: str
    base_price: int  # kopecks per 30 days (for formula-based products)
    trial_days: int
    is_bundle: bool
    includes: list[str] = field(default_factory=list)
    product_type: str = "other"  # "vpn" | "mtproto" | "whatsapp" | "bundle" | "other"
    devices: int = 0  # device count (for VPN products)
    prices: dict[str, dict[int, float]] | None = None  # fixed prices {currency: {duration: price}}


class ProductCatalog:
    def __init__(self, file_path: Path | None = None) -> None:
        file_path = file_path or DEFAULT_PRODUCTS_PATH

        if not file_path.is_file():
            logger.error(f"Products file '{file_path}' does not exist.")
            raise FileNotFoundError(f"Products file '{file_path}' does not exist.")

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse '{file_path}'. Invalid JSON.")
            raise ValueError(f"'{file_path}' is not a valid JSON file.")

        raw_products = data.get("products", {})
        self._products: dict[str, Product] = {}
        for slug, info in raw_products.items():
            # Parse fixed prices if present
            raw_prices = info.get("prices")
            prices = None
            if raw_prices:
                prices = {
                    currency: {int(dur): price for dur, price in dur_prices.items()}
                    for currency, dur_prices in raw_prices.items()
                }

            self._products[slug] = Product(
                slug=slug,
                name=info["name"],
                emoji=info.get("emoji", ""),
                description=info.get("description", ""),
                base_price=info.get("base_price", 0),
                trial_days=info.get("trial_days", 0),
                is_bundle=info.get("is_bundle", False),
                includes=info.get("includes", []),
                product_type=info.get("product_type", "other"),
                devices=info.get("devices", 0),
                prices=prices,
            )

        self._durations: list[int] = data.get("durations", [30, 90, 180, 365])
        self._discounts: dict[int, float] = {
            int(k): v for k, v in data.get("discounts", {}).items()
        }
        self._stars_rate: float = data.get("stars_rate", 1.8)

        # --- Load location-scoped VPN profiles ---
        self._vpn_profiles: dict[str, VpnProfile] = {}
        profiles_path = DEFAULT_VPN_PROFILES_PATH
        legacy_operators_path = DEFAULT_OPERATORS_PATH
        if profiles_path.is_file():
            try:
                with open(profiles_path, "r") as f:
                    profiles_data = json.load(f)
                for info in profiles_data.get("profiles", []):
                    profile = VpnProfile(
                        slug=info["slug"],
                        name=info["name"],
                        emoji=info.get("emoji", ""),
                        inbound_remark=info["inbound_remark"],
                        order=info.get("order", 0),
                        client_flow=info.get("client_flow", ""),
                        locations=info.get("locations", []),
                        kind=info.get("kind", "universal"),
                        legacy_slugs=info.get("legacy_slugs", []),
                    )
                    self._vpn_profiles[profile.slug] = profile
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse vpn profiles file: {e}")
        elif legacy_operators_path.is_file():
            logger.warning(
                "vpn_profiles.json not found, falling back to operators.json legacy behavior."
            )
            try:
                with open(legacy_operators_path, "r") as f:
                    operators_data = json.load(f)
                for info in operators_data.get("operators", []):
                    profile = VpnProfile(
                        slug=info["slug"],
                        name=info["name"],
                        emoji=info.get("emoji", ""),
                        inbound_remark=info["inbound_remark"],
                        order=info.get("order", 0),
                        client_flow=info.get("client_flow", ""),
                        locations=["Amsterdam"],
                        kind="operator",
                        legacy_slugs=[info["slug"]],
                    )
                    self._vpn_profiles[profile.slug] = profile
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse legacy operators file: {e}")
        else:
            logger.warning(
                "vpn_profiles.json and operators.json not found, VPN profile selection disabled."
            )

        logger.info(
            f"ProductCatalog loaded: {len(self._products)} products, "
            f"{len(self._durations)} durations, {len(self._vpn_profiles)} vpn profiles, "
            f"stars_rate={self._stars_rate}"
        )

    # --- General product access ---

    def get_product(self, slug: str) -> Product | None:
        return self._products.get(slug)

    def get_all_products(self) -> list[Product]:
        return list(self._products.values())

    def get_bundles(self) -> list[Product]:
        return [p for p in self._products.values() if p.is_bundle]

    def get_individual_products(self) -> list[Product]:
        return [p for p in self._products.values() if not p.is_bundle]

    def get_durations(self) -> list[int]:
        return self._durations

    def get_discount_percent(self, duration: int) -> int:
        """Discount percentage as integer (0, 13, 20, 33)."""
        discount = self._discounts.get(duration, 0)
        return round(discount * 100)

    # --- VPN-specific access (replaces PlanService) ---

    def get_vpn_products(self) -> list[Product]:
        """All VPN products, sorted by devices."""
        return sorted(
            [p for p in self._products.values() if p.product_type == "vpn"],
            key=lambda p: p.devices,
        )

    def get_vpn_product_by_devices(self, devices: int) -> Product | None:
        """Find VPN product by device count."""
        return next(
            (p for p in self._products.values()
             if p.product_type == "vpn" and p.devices == devices),
            None,
        )

    # --- Universal price lookup ---

    def get_price(self, slug: str, currency: str, duration: int) -> float | None:
        """Universal price lookup.
        VPN: fixed price from prices[currency][duration].
        Others: formula base_price * months * discount, converted to currency.
        """
        product = self._products.get(slug)
        if not product:
            return None
        if product.prices:
            return product.prices.get(currency, {}).get(duration)
        # Formula-based pricing (for non-VPN)
        if currency == "XTR":
            return self.calculate_price_stars(slug, duration)
        return self.calculate_price_rub(slug, duration)

    # --- Formula-based pricing (for non-VPN products) ---

    def calculate_price(self, slug: str, duration: int) -> int:
        """Price in kopecks with period discount applied."""
        product = self._products.get(slug)
        if not product:
            raise ValueError(f"Unknown product: {slug}")

        discount = self._discounts.get(duration, 0)
        months = duration / 30
        price = product.base_price * months * (1 - discount)
        return round(price)

    def calculate_price_rub(self, slug: str, duration: int) -> int:
        """Price in rubles (kopecks / 100, rounded)."""
        kopecks = self.calculate_price(slug, duration)
        return round(kopecks / 100)

    def calculate_price_stars(self, slug: str, duration: int) -> int:
        """Price in Telegram Stars."""
        rub = self.calculate_price_rub(slug, duration)
        return max(1, round(rub / self._stars_rate))

    def get_prices_rub(self, slug: str) -> dict[int, int]:
        """All prices for a product: {30: 49, 90: 128, 180: 235, 365: 394}."""
        return {d: self.calculate_price_rub(slug, d) for d in self._durations}

    def get_prices_stars(self, slug: str) -> dict[int, int]:
        """All Stars prices for a product: {30: 27, 90: 71, ...}."""
        return {d: self.calculate_price_stars(slug, d) for d in self._durations}

    @property
    def stars_rate(self) -> float:
        return self._stars_rate

    # --- Operator access ---

    def get_vpn_profiles(
        self,
        location: str | None = None,
        kind: str | None = None,
    ) -> list[VpnProfile]:
        profiles = self._vpn_profiles.values()
        if location is not None:
            profiles = [profile for profile in profiles if location in profile.locations]
        else:
            profiles = list(profiles)

        if kind is not None:
            profiles = [profile for profile in profiles if profile.kind == kind]

        return sorted(profiles, key=lambda profile: profile.order)

    def get_vpn_profile(self, slug: str, location: str | None = None) -> VpnProfile | None:
        profile = self._vpn_profiles.get(slug)
        if not profile:
            return None
        if location and location not in profile.locations:
            return None
        return profile

    def get_default_vpn_profile(self, location: str | None) -> VpnProfile | None:
        profiles = self.get_vpn_profiles(location=location)
        return profiles[0] if profiles else None

    def resolve_vpn_profile(
        self,
        location: str | None,
        profile_slug: str | None = None,
        legacy_slug: str | None = None,
    ) -> VpnProfile | None:
        if profile_slug:
            profile = self.get_vpn_profile(profile_slug, location=location)
            if profile:
                return profile

        if legacy_slug and location:
            for profile in self.get_vpn_profiles(location=location):
                if legacy_slug in profile.legacy_slugs:
                    return profile

        return self.get_default_vpn_profile(location)

    def get_operators(self) -> list[Operator]:
        """Legacy helper for bot flows: Amsterdam-only switchable profiles."""
        return self.get_vpn_profiles(location="Amsterdam")

    def get_operator(self, slug: str) -> Operator | None:
        return self.resolve_vpn_profile(location="Amsterdam", profile_slug=slug, legacy_slug=slug)

    def get_operator_inbound_remark(self, slug: str) -> str | None:
        profile = self.get_operator(slug)
        return profile.inbound_remark if profile else None

    def get_operator_client_flow(self, slug: str) -> str | None:
        profile = self.get_operator(slug)
        return profile.client_flow if profile else None
