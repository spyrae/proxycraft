interface FaqItem {
  question: string;
  answer: string;
}

export const faqRu: FaqItem[] = [
  {
    question: 'Что такое ProxyCraft?',
    answer: 'ProxyCraft — это сервис для безопасного и свободного доступа к интернету. Мы предлагаем три продукта: Full VPN (защита всего трафика), Telegram Proxy (доступ к Telegram) и WhatsApp Proxy (звонки и сообщения в WhatsApp).',
  },
  {
    question: 'Чем VLESS отличается от обычного VPN?',
    answer: 'VLESS — это современный протокол, который маскирует VPN-трафик под обычный HTTPS. Провайдеры и DPI-системы не могут отличить его от обычного веб-серфинга, поэтому VLESS работает даже там, где обычные VPN заблокированы.',
  },
  {
    question: 'Работает ли ProxyCraft в Китае и Иране?',
    answer: 'Да. Благодаря использованию VLESS протокола через Cloudflare CDN, наш VPN работает в странах с жёсткой интернет-цензурой, включая Китай, Иран и Россию.',
  },
  {
    question: 'Есть ли бесплатный пробный период?',
    answer: 'Да! Full VPN — 7 дней бесплатно, Telegram Proxy и WhatsApp Proxy — 3 дня бесплатно. Без привязки карты.',
  },
  {
    question: 'Какие способы оплаты доступны?',
    answer: 'Мы принимаем оплату в рублях через ЮKassa, ЮMoney, а также в Telegram Stars. Для пользователей за рубежом доступна оплата криптовалютой.',
  },
  {
    question: 'На каких устройствах работает ProxyCraft?',
    answer: 'VPN работает на iOS, Android, Windows, macOS и Linux через приложение Happ. Telegram Proxy работает прямо в приложении Telegram. WhatsApp Proxy настраивается в настройках WhatsApp.',
  },
  {
    question: 'Что такое приложение Happ?',
    answer: 'Happ — это приложение для подключения к VPN. Доступно в App Store и Google Play. После получения конфигурации в боте, вы просто импортируете её в Happ одним нажатием.',
  },
  {
    question: 'Вы храните логи?',
    answer: 'Нет. Мы не ведём журналов подключений, не отслеживаем вашу активность и не храним историю посещённых сайтов. Ваша приватность — наш приоритет.',
  },
  {
    question: 'Как работает реферальная программа?',
    answer: 'Пригласите друга по реферальной ссылке — получите +10 дней к подписке. Если ваш друг тоже кого-то пригласит, вы получите ещё +3 дня. Бонусы начисляются автоматически.',
  },
  {
    question: 'Как подключиться?',
    answer: 'Откройте @proxycraftapp_bot в Telegram, выберите продукт и тарифный план. Бот выдаст конфигурацию и пошаговую инструкцию по подключению для вашего устройства.',
  },
  {
    question: 'Есть ли ограничения по трафику?',
    answer: 'Нет. Все тарифные планы включают безлимитный трафик. Стримьте видео, скачивайте файлы, работайте — без ограничений.',
  },
  {
    question: 'Что делать, если не работает?',
    answer: 'Напишите в @proxycraftapp_bot команду /support — наша поддержка работает 24/7 и поможет решить любую проблему с подключением.',
  },
];

export const faqEn: FaqItem[] = [
  {
    question: 'What is ProxyCraft?',
    answer: 'ProxyCraft is a service for secure and unrestricted internet access. We offer three products: Full VPN (all traffic protection), Telegram Proxy (Telegram access) and WhatsApp Proxy (WhatsApp calls and messages).',
  },
  {
    question: 'How is VLESS different from regular VPN?',
    answer: 'VLESS is a modern protocol that disguises VPN traffic as regular HTTPS. ISPs and DPI systems cannot distinguish it from normal web browsing, so VLESS works even where regular VPNs are blocked.',
  },
  {
    question: 'Does ProxyCraft work in China and Iran?',
    answer: 'Yes. Thanks to VLESS protocol routed through Cloudflare CDN, our VPN works in countries with strict internet censorship, including China, Iran and Russia.',
  },
  {
    question: 'Is there a free trial?',
    answer: 'Yes! Full VPN — 7 days free, Telegram Proxy and WhatsApp Proxy — 3 days free. No credit card required.',
  },
  {
    question: 'What payment methods are available?',
    answer: 'We accept payments in rubles via YooKassa, YooMoney, and in Telegram Stars. Cryptocurrency payments are also available for international users.',
  },
  {
    question: 'What devices does ProxyCraft support?',
    answer: 'VPN works on iOS, Android, Windows, macOS and Linux via the Happ app. Telegram Proxy works directly in the Telegram app. WhatsApp Proxy is configured in WhatsApp settings.',
  },
  {
    question: 'What is the Happ app?',
    answer: 'Happ is the app for connecting to VPN. Available on App Store and Google Play. After receiving your configuration from the bot, you simply import it into Happ with one tap.',
  },
  {
    question: 'Do you keep logs?',
    answer: 'No. We do not log connections, track your activity or store browsing history. Your privacy is our priority.',
  },
  {
    question: 'How does the referral program work?',
    answer: 'Invite a friend with your referral link — get +10 days added to your subscription. If your friend also invites someone, you get an additional +3 days. Bonuses are applied automatically.',
  },
  {
    question: 'How do I connect?',
    answer: 'Open @proxycraftapp_bot in Telegram, choose a product and plan. The bot will provide your configuration and step-by-step setup instructions for your device.',
  },
  {
    question: 'Are there traffic limits?',
    answer: 'No. All plans include unlimited traffic. Stream videos, download files, work — without any restrictions.',
  },
  {
    question: 'What if it doesn\'t work?',
    answer: 'Message @proxycraftapp_bot with the /support command — our support team works 24/7 and will help resolve any connection issue.',
  },
];
