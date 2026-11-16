import type { Metadata } from "next";
import { PageHero } from "@/components/site/PageHero";
import { Shell } from "@/components/site/primitives";
import { ContactDesk } from "@/components/contact/ContactDesk";
import { businessDivisions } from "@/data/divisions";

export const metadata: Metadata = {
  title: "Request for Quotation",
  description: "Submit a commercial trade enquiry or request for quotation to EDEN BOUNTY Sdn. Bhd.",
  alternates: { canonical: "/rfq" },
};

export default async function RfqPage({
  searchParams,
}: {
  searchParams: Promise<{ division?: string | string[] }>;
}) {
  const { division } = await searchParams;
  const requested = Array.isArray(division) ? division[0] : division;
  const initialDivisionId = businessDivisions.some((d) => d.id === requested) ? requested : undefined;

  return (
    <>
      <PageHero
        eyebrow="Contact · Enquiry desk"
        title="Commercial enquiries & RFQ."
        intro="Select a commercial trading division and submit an RFQ online, or prepare an email draft to review and send yourself."
      />
      <section id="inquiry" className="eb-section scroll-mt-24" aria-labelledby="rfq-heading">
        <Shell>
          <h2 id="rfq-heading" className="sr-only">Request for quotation form</h2>
          <ContactDesk initialDivisionId={initialDivisionId} />
        </Shell>
      </section>
    </>
  );
}
