import { describe, it, expect } from "vitest";
import {
  INDUSTRY_TEMPLATES,
  fillPlaceholders,
  getTemplateForIndustry,
} from "./industry-prompts";

describe("industry-prompts", () => {
  describe("INDUSTRY_TEMPLATES", () => {
    it("includes every industry we advertise in the picker", () => {
      const keys = INDUSTRY_TEMPLATES.map((t) => t.key);
      expect(keys).toContain("Dental");
      expect(keys).toContain("Medical");
      expect(keys).toContain("Software");
      expect(keys).toContain("Other");
      // Sanity: every entry is properly formed
      for (const t of INDUSTRY_TEMPLATES) {
        expect(t.key).toBeTruthy();
        expect(t.label).toBeTruthy();
        expect(t.prompt.length).toBeGreaterThan(100);
      }
    });

    it("every template mentions {{org_name}} so admins get placeholder substitution", () => {
      for (const t of INDUSTRY_TEMPLATES) {
        expect(t.prompt).toContain("{{org_name}}");
      }
    });
  });

  describe("fillPlaceholders", () => {
    it("substitutes known placeholders", () => {
      const out = fillPlaceholders("Hello {{org_name}}, welcome to {{industry}}.", {
        org_name: "Acme",
        industry: "Dental",
      });
      expect(out).toBe("Hello Acme, welcome to Dental.");
    });

    it("leaves unknown placeholders in place so admins can see and fix them", () => {
      const out = fillPlaceholders("Contact {{phone}} — do not skip {{unknown_key}}.", {
        // phone deliberately omitted
      });
      expect(out).toBe("Contact {{phone}} — do not skip {{unknown_key}}.");
    });

    it("treats empty string as missing (does not substitute)", () => {
      const out = fillPlaceholders("Name: {{org_name}}", { org_name: "" });
      expect(out).toBe("Name: {{org_name}}");
    });

    it("trims whitespace-only values (treats them as missing)", () => {
      const out = fillPlaceholders("Name: {{org_name}}", { org_name: "   " });
      expect(out).toBe("Name: {{org_name}}");
    });
  });

  describe("getTemplateForIndustry", () => {
    it("returns the matching template when key exists", () => {
      const t = getTemplateForIndustry("Dental");
      expect(t.key).toBe("Dental");
    });

    it("falls back to Other for unknown industries", () => {
      const t = getTemplateForIndustry("MartianColonization");
      expect(t.key).toBe("Other");
    });

    it("falls back to Other for null/undefined industry", () => {
      expect(getTemplateForIndustry(null).key).toBe("Other");
      expect(getTemplateForIndustry(undefined).key).toBe("Other");
    });
  });
});
