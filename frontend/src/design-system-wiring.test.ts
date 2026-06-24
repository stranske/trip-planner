import { describe, expect, it } from "vitest";

import indexHtml from "../index.html?raw";
import mainSource from "./main.tsx?raw";

function expectDesignSystemImportOrder(source: string) {
  const expectedImports = [
    'import "./design-system/ds-tokens.css";',
    'import "./design-system/ds-components.css";',
    'import "./design-system/reconcile.css";',
    'import "./styles.css";',
  ];
  const positions = expectedImports.map((statement) => source.indexOf(statement));

  expect(positions, "all design-system stylesheet imports are present").not.toContain(-1);
  expect(positions, "design-system styles load before app styles").toEqual(
    [...positions].sort((left, right) => left - right)
  );
}

describe("design-system wiring", () => {
  it("loads shared design-system styles before app styles", () => {
    expectDesignSystemImportOrder(mainSource);
  });

  it("detects a missing required stylesheet import", () => {
    const brokenSource = mainSource.replace('import "./design-system/ds-components.css";', "");

    expect(() => expectDesignSystemImportOrder(brokenSource)).toThrow();
  });

  it("mounts the app under the fleet theme-air root class", () => {
    expect(indexHtml).toContain('<div id="root" class="ds theme-air"></div>');
    expect(indexHtml).not.toContain("theme-paper");
  });
});
