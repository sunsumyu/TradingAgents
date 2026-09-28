// Barrel for components/shared. Note: nothing imports the barrel itself —
// consumers use direct paths (`../shared/Markdown`, `../shared/chartTheme`).
// The old `DataTable` implementation was archived in ticket 10; GenericDataTable
// (ticket 05) supersedes it. See src/_archive/README.md.
export { default as GenericDataTable, FeatureDataTable, rowsFromData } from "./GenericDataTable";
export { default as Markdown } from "./Markdown";
export { chartTheme, withTheme } from "./chartTheme";
