import React from "react";
import { CheckCircle2, Lock, Sparkles, Award } from "lucide-react";

export default function BadgeCard({ badge }) {
  const { id, label, icon, description, condition, earned, earned_at } = badge;

  const formattedDate = earned_at
    ? new Date(earned_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric"
      })
    : null;

  return (
    <div
      style={{
        backgroundColor: earned ? "#FFFFFF" : "#F8FAFC",
        border: earned ? "1px solid #CCFBF1" : "1px solid #E2E8F0",
        borderRadius: "14px",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        boxShadow: earned
          ? "0 2px 8px -2px rgba(15, 118, 110, 0.1), 0 1px 3px rgba(0, 0, 0, 0.05)"
          : "none",
        opacity: earned ? 1 : 0.7,
        transition: "all 0.2s ease-in-out",
        position: "relative",
        overflow: "hidden"
      }}
    >
      {earned && (
        <div
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            width: "36px",
            height: "36px",
            background: "linear-gradient(135deg, transparent 50%, #0F766E20 50%)",
            borderBottomLeftRadius: "8px"
          }}
        />
      )}

      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "12px"
          }}
        >
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "12px",
              backgroundColor: earned ? "#F0FDFA" : "#F1F5F9",
              border: earned ? "1px solid #99F6E4" : "1px solid #CBD5E1",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "22px"
            }}
          >
            {icon || "🏆"}
          </div>

          <span
            style={{
              fontSize: "10px",
              fontWeight: 700,
              padding: "3px 8px",
              borderRadius: "12px",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              backgroundColor: earned ? "#ECFDF5" : "#F1F5F9",
              color: earned ? "#047857" : "#64748B",
              border: earned ? "1px solid #A7F3D0" : "1px solid #E2E8F0",
              textTransform: "uppercase"
            }}
          >
            {earned ? (
              <>
                <CheckCircle2 size={12} color="#047857" /> Earned
              </>
            ) : (
              <>
                <Lock size={12} color="#64748B" /> Locked
              </>
            )}
          </span>
        </div>

        <h4
          style={{
            fontSize: "14px",
            fontWeight: 800,
            color: earned ? "#0F172A" : "#475569",
            margin: "0 0 4px 0",
            letterSpacing: "-0.01em"
          }}
        >
          {label}
        </h4>

        <p
          style={{
            fontSize: "12px",
            color: "#64748B",
            lineHeight: 1.45,
            margin: "0 0 10px 0"
          }}
        >
          {description}
        </p>
      </div>

      <div
        style={{
          borderTop: "1px dashed #E2E8F0",
          paddingTop: "8px",
          marginTop: "4px",
          fontSize: "10px",
          color: earned ? "#0F766E" : "#94A3B8",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between"
        }}
      >
        <span>{earned ? `Earned ${formattedDate || ""}` : condition || "Scenario Requirement"}</span>
      </div>
    </div>
  );
}
