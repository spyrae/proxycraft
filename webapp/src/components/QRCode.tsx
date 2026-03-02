import { QRCodeSVG } from 'qrcode.react';

interface Props {
  value: string;
  size?: number;
}

export function QRCode({ value, size = 180 }: Props) {
  return (
    <div className="flex justify-center">
      <div
        className="p-4 rounded-2xl"
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid var(--border)',
          boxShadow: '0 0 20px rgba(16, 185, 129, 0.1)',
        }}
      >
        <QRCodeSVG
          value={value}
          size={size}
          bgColor="#ffffff"
          fgColor="#0A0E17"
          level="M"
        />
      </div>
    </div>
  );
}
