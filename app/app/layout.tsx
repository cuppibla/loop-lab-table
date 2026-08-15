import "./globals.css";

export const metadata = {
  title: "Table for N",
  description: "One table. N people. How many actually ate?",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
