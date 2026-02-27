import { QRCodeSVG } from 'qrcode.react';

interface Props {
  value: string;
  size?: number;
}

export function QRCode({ value, size = 180 }: Props) {
  return (
    <div className="flex justify-center p-4 rounded-xl" style={{ backgroundColor: '#ffffff' }}>
      <QRCodeSVG
        value={value}
        size={size}
        bgColor="#ffffff"
        fgColor="#000000"
        level="M"
      />
    </div>
  );
}
