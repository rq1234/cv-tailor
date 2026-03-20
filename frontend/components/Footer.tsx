import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t mt-12 py-6 px-4">
      <div className="mx-auto max-w-7xl flex justify-between items-center text-xs text-muted-foreground">
        <p>© {new Date().getFullYear()} CV Tailor</p>
        <Link href="/privacy" className="hover:text-foreground transition-colors">
          Privacy Policy
        </Link>
      </div>
    </footer>
  );
}
