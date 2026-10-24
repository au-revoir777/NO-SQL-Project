// cytoscape-svg 0.4.0 ships no types: it registers `cy.svg(options)` as an extension.
declare module "cytoscape-svg" {
  import type cytoscape from "cytoscape";

  const ext: cytoscape.Ext;
  export default ext;
}
