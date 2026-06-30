import "./globals.css";
import Script from "next/script";

export const metadata = {
  title: "Strontium Agent",
  description: "Strontium Agent",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        {/* 런타임 환경변수 주입 — Docker 컨테이너 시작 시 entrypoint가 생성 */}
        <Script src="/env-config.js" strategy="beforeInteractive" />
        {children}
      </body>
    </html>
  );
}
