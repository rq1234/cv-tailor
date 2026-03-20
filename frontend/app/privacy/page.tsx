export default function PrivacyPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold">Privacy Policy</h1>
        <p className="text-sm text-muted-foreground">Last updated: March 2025</p>
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">What we collect</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          When you upload a CV, we extract and store the text content — your work experience, education,
          skills, and projects as structured data. We also store the job descriptions you paste in, the
          AI-generated tailoring suggestions, and basic profile information parsed from your CV (name,
          email, phone, location).
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">What we do not store</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          We do not store your original PDF or DOCX file. When you upload a CV, the file is parsed for
          text and then discarded — only the extracted content is kept. Generated PDF and DOCX exports
          are streamed directly to your browser and are never saved to our servers.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">How your data is used</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Your data is used solely to provide the CV tailoring service. We do not sell, share, or
          disclose your data to third parties for marketing or any other purpose.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Third-party AI processing</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          To generate tailoring suggestions, your CV text and job description are sent to the OpenAI
          API. OpenAI does not use API inputs to train its models by default. You can review
          OpenAI&apos;s data usage policy at{" "}
          <span className="font-medium text-foreground">platform.openai.com/docs/privacy</span>.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Data hosting</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Your data is stored in a PostgreSQL database hosted by Supabase on AWS infrastructure. The
          backend API runs on AWS App Runner and the frontend is hosted on AWS Amplify. All data is
          encrypted in transit over HTTPS.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Deleting your data</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          You can permanently delete your account and all associated data at any time from the{" "}
          <span className="font-medium text-foreground">Settings</span> page. This removes all your
          CV content, applications, tailoring history, and your login credentials. Deletion is
          immediate and irreversible.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Security</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          All data in transit is encrypted over HTTPS. Database access requires authentication and
          all queries are scoped to your account — no user can access another user&apos;s data.
        </p>
      </section>
    </div>
  );
}
