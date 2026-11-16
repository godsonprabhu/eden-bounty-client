"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import { AdminApiError, apiGetEnquiryDetail } from "@/lib/admin-api";
import { EnquiryDetailResponseData, EnquiryNoteItem } from "@/types/admin";
import { EnquiryDossierHeader } from "@/components/admin/enquiries/detail/EnquiryDossierHeader";
import { SubmitterContactCard } from "@/components/admin/enquiries/detail/SubmitterContactCard";
import { CommercialRequirementsCard } from "@/components/admin/enquiries/detail/CommercialRequirementsCard";
import { EnquiryCustomerCard } from "@/components/admin/portal/EnquiryCustomerCard";
import { UnifiedTimelineCard } from "@/components/admin/enquiries/detail/UnifiedTimelineCard";
import { InternalNotesSection } from "@/components/admin/enquiries/detail/InternalNotesSection";
import { AssignmentHistoryCard } from "@/components/admin/enquiries/detail/AssignmentHistoryCard";
import { StatusHistoryCard } from "@/components/admin/enquiries/detail/StatusHistoryCard";
import { EnquiryDossierSkeleton } from "@/components/admin/enquiries/detail/EnquiryDossierSkeleton";
import { EnquiryDossierNotFound } from "@/components/admin/enquiries/detail/EnquiryDossierNotFound";
import { EnquiryDossierError } from "@/components/admin/enquiries/detail/EnquiryDossierError";
import { AssignEnquiryModal } from "@/components/admin/enquiries/detail/AssignEnquiryModal";
import { UpdateStatusModal } from "@/components/admin/enquiries/detail/UpdateStatusModal";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function EnquiryDetailPage({ params }: PageProps) {
  const { id } = use(params);

  const [dossier, setDossier] = useState<EnquiryDetailResponseData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isNotFound, setIsNotFound] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  // Workflow Dialog States
  const [isAssignModalOpen, setIsAssignModalOpen] = useState<boolean>(false);
  const [isStatusModalOpen, setIsStatusModalOpen] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;

    apiGetEnquiryDetail(id)
      .then((data) => {
        if (isMounted) {
          setDossier(data);
          setErrorMessage(null);
          setIsNotFound(false);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          if (err instanceof AdminApiError && err.status === 404) {
            setIsNotFound(true);
            setDossier(null);
          } else {
            const msg = err instanceof Error ? err.message : "Failed to load enquiry dossier";
            setErrorMessage(msg);
            setDossier(null);
          }
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [id, refreshKey]);

  const handleRefresh = useCallback(() => {
    setIsLoading(true);
    setRefreshKey((k) => k + 1);
  }, []);

  const handleAssignSuccess = useCallback((updatedDossier: EnquiryDetailResponseData) => {
    setDossier(updatedDossier);
  }, []);

  const handleStatusSuccess = useCallback((updatedDossier: EnquiryDetailResponseData) => {
    setDossier(updatedDossier);
  }, []);

  const handleNoteAdded = useCallback((newNote: EnquiryNoteItem) => {
    setDossier((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        notes: [newNote, ...(prev.notes || [])],
      };
    });
  }, []);

  if (isLoading) {
    return <EnquiryDossierSkeleton />;
  }

  if (isNotFound) {
    return <EnquiryDossierNotFound id={id} />;
  }

  if (errorMessage || !dossier) {
    return (
      <EnquiryDossierError
        message={errorMessage || "Unable to retrieve enquiry details"}
        onRetry={handleRefresh}
      />
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Dossier Header */}
      <EnquiryDossierHeader
        dossier={dossier}
        onRefresh={handleRefresh}
        isLoading={isLoading}
        onOpenAssignModal={() => setIsAssignModalOpen(true)}
        onOpenStatusModal={() => setIsStatusModalOpen(true)}
      />

      {/* Main Asymmetric Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Main Operational Column (8 of 12 columns) */}
        <div className="lg:col-span-8 space-y-6">
          {/* Commercial Specifications Snapshot */}
          <CommercialRequirementsCard dossier={dossier} />

          {/* Unified Chronological Operational Timeline */}
          <EnquiryCustomerCard
            enquiry={{
              id: dossier.id,
              reference_number: dossier.reference_number,
              product_focus: dossier.product_focus,
              business_email: dossier.business_email,
            }}
          />

          <UnifiedTimelineCard dossier={dossier} />

          {/* Confidential Internal Operational Notes */}
          <InternalNotesSection
            notes={dossier.notes || []}
            enquiryId={id}
            onNoteAdded={handleNoteAdded}
          />
        </div>

        {/* Side Administrative & Entity Column (4 of 12 columns) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Submitter & Entity Snapshot */}
          <SubmitterContactCard dossier={dossier} />

          {/* Assignment Routing History */}
          <AssignmentHistoryCard assignments={dossier.assignments || []} />

          {/* Status Progression History */}
          <StatusHistoryCard statusHistory={dossier.status_history || []} />
        </div>
      </div>

      {/* Interactive Workflow Modals */}
      {isAssignModalOpen && (
        <AssignEnquiryModal
          isOpen={isAssignModalOpen}
          onClose={() => setIsAssignModalOpen(false)}
          dossier={dossier}
          onSuccess={handleAssignSuccess}
        />
      )}

      {isStatusModalOpen && (
        <UpdateStatusModal
          isOpen={isStatusModalOpen}
          onClose={() => setIsStatusModalOpen(false)}
          dossier={dossier}
          onSuccess={handleStatusSuccess}
        />
      )}
    </div>
  );
}
