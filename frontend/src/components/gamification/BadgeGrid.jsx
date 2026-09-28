import React, { useState } from "react";
import BadgeCard from "./BadgeCard";
import { Award, Lock, CheckCircle2, Shield } from "lucide-react";

export default function BadgeGrid({ badges = [] }) {
  const [filter, setFilter] = useState("all"); // 'all' | 'earned' | 'locked'

  const earnedCount = badges.filter((b) => b.earned).length;
  const totalCount = badges.length;

  const filteredBadges = badges.filter((badge) => {
    if (filter === "earned") return badge.earned;
    if (filter === "locked") return !badge.earned;
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Filter & Summary Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          backgroundColor: "#FFFFFF",
          padding: "12px 16px",
          borderRadius: "12px",
          border: "1px solid #E2E8F0"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Award size={20} color="#0F766E" />
          <div>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#0F172A" }}>
              Simulation Achievements
            </span>
            <span
              style={{
                display: "block",
                fontSize: "11px",
                color: "#64748B"
              }}
            >
              {earnedCount} of {totalCount} Badges Unlocked
            </span>
          </div>
        </div>

        {/* Segmented Filter Control */}
        <div
          style={{
            display: "flex",
            backgroundColor: "#F1F5F9",
            borderRadius: "8px",
            padding: "3px",
            fontSize: "11px",
            fontWeight: 600
          }}
        >
          <button
            onClick={() => setFilter("all")}
            style={{
              padding: "4px 12px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              backgroundColor: filter === "all" ? "#FFFFFF" : "transparent",
              color: filter === "all" ? "#0F766E" : "#64748B",
              fontWeight: filter === "all" ? 700 : 500,
              boxShadow: filter === "all" ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
              transition: "all 0.15s"
            }}
          >
            All ({totalCount})
          </button>
          <button
            onClick={() => setFilter("earned")}
            style={{
              padding: "4px 12px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              backgroundColor: filter === "earned" ? "#FFFFFF" : "transparent",
              color: filter === "earned" ? "#0F766E" : "#64748B",
              fontWeight: filter === "earned" ? 700 : 500,
              boxShadow: filter === "earned" ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
              transition: "all 0.15s"
            }}
          >
            Unlocked ({earnedCount})
          </button>
          <button
            onClick={() => setFilter("locked")}
            style={{
              padding: "4px 12px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              backgroundColor: filter === "locked" ? "#FFFFFF" : "transparent",
              color: filter === "locked" ? "#0F766E" : "#64748B",
              fontWeight: filter === "locked" ? 700 : 500,
              boxShadow: filter === "locked" ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
              transition: "all 0.15s"
            }}
          >
            Locked ({totalCount - earnedCount})
          </button>
        </div>
      </div>

      {/* Badges Grid */}
      {filteredBadges.length === 0 ? (
        <div
          style={{
            padding: "32px",
            textAlign: "center",
            backgroundColor: "#F8FAFC",
            borderRadius: "14px",
            border: "1px dashed #CBD5E1",
            color: "#64748B",
            fontSize: "13px"
          }}
        >
          No badges match the selected filter.
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "16px"
          }}
        >
          {filteredBadges.map((badge) => (
            <BadgeCard key={badge.id} badge={badge} />
          ))}
        </div>
      )}
    </div>
  );
}
