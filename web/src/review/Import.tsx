import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, J } from "../api";
import { Card, ErrorNote } from "../ui";

export default function ImportLinkedin() {
  const [name, setName] = useState("");
  const m = useMutation({ mutationFn: (csv: string) => api<J>("/import/linkedin", "POST", { csv }) });
  const pick = async (f: File | undefined) => {
    if (!f) return;
    setName(f.name);
    m.mutate(await f.text());
  };
  return (
    <Card title="Import your LinkedIn connections">
      <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm text-slate-600">
        <li>On LinkedIn: Settings, Data privacy, <b>Get a copy of your data</b>, request the larger archive (ready within about 24 hours).</li>
        <li>Open the downloaded zip and pick <b>Connections.csv</b> below. Nothing is scraped; the file is your own data.</li>
        <li>Then run <b>rank</b> (Search &amp; run). Connections get a score bonus and show as &quot;your LinkedIn connection&quot;.</li>
      </ol>
      <input type="file" accept=".csv,text/csv" onChange={(e) => pick(e.target.files?.[0])} />
      <ErrorNote error={m.error} />
      {m.isPending && <p className="mt-2 text-sm">Importing {name}…</p>}
      {m.data && (
        <p className="mt-2 text-sm text-green-700">
          {m.data.imported} connections imported ({m.data.with_email} with an email, {m.data.skipped_no_company} skipped without a company).{" "}
          <Link className="underline" to="/review/contacts">See contacts</Link>
        </p>
      )}
    </Card>
  );
}
