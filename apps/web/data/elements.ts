/**
 * Periodic table data — all 118 elements with their visual grid position.
 *
 *  period:  visual row (1–7 main table, 8 = lanthanides strip, 9 = actinides strip)
 *  group:   visual column (1–18; lanthanides/actinides span groups 3–17 in their strip)
 *  category: drives color in the picker UI
 */
export type ElementCategory =
  | "alkali"
  | "alkaline"
  | "transition"
  | "post-transition"
  | "metalloid"
  | "nonmetal"
  | "halogen"
  | "noble"
  | "lanthanide"
  | "actinide";

export interface PeriodicElement {
  symbol: string;
  name: string;
  number: number;
  period: number;   // visual row (1..9)
  group: number;    // visual column (1..18)
  category: ElementCategory;
}

// Helper to build the table compactly
const E = (
  symbol: string, name: string, number: number,
  period: number, group: number, category: ElementCategory,
): PeriodicElement => ({ symbol, name, number, period, group, category });

export const ELEMENTS: PeriodicElement[] = [
  // Period 1
  E("H",  "Hydrogen",   1, 1, 1,  "nonmetal"),
  E("He", "Helium",     2, 1, 18, "noble"),

  // Period 2
  E("Li", "Lithium",    3, 2, 1,  "alkali"),
  E("Be", "Beryllium",  4, 2, 2,  "alkaline"),
  E("B",  "Boron",      5, 2, 13, "metalloid"),
  E("C",  "Carbon",     6, 2, 14, "nonmetal"),
  E("N",  "Nitrogen",   7, 2, 15, "nonmetal"),
  E("O",  "Oxygen",     8, 2, 16, "nonmetal"),
  E("F",  "Fluorine",   9, 2, 17, "halogen"),
  E("Ne", "Neon",      10, 2, 18, "noble"),

  // Period 3
  E("Na", "Sodium",    11, 3, 1,  "alkali"),
  E("Mg", "Magnesium", 12, 3, 2,  "alkaline"),
  E("Al", "Aluminium", 13, 3, 13, "post-transition"),
  E("Si", "Silicon",   14, 3, 14, "metalloid"),
  E("P",  "Phosphorus",15, 3, 15, "nonmetal"),
  E("S",  "Sulfur",    16, 3, 16, "nonmetal"),
  E("Cl", "Chlorine",  17, 3, 17, "halogen"),
  E("Ar", "Argon",     18, 3, 18, "noble"),

  // Period 4
  E("K",  "Potassium", 19, 4, 1,  "alkali"),
  E("Ca", "Calcium",   20, 4, 2,  "alkaline"),
  E("Sc", "Scandium",  21, 4, 3,  "transition"),
  E("Ti", "Titanium",  22, 4, 4,  "transition"),
  E("V",  "Vanadium",  23, 4, 5,  "transition"),
  E("Cr", "Chromium",  24, 4, 6,  "transition"),
  E("Mn", "Manganese", 25, 4, 7,  "transition"),
  E("Fe", "Iron",      26, 4, 8,  "transition"),
  E("Co", "Cobalt",    27, 4, 9,  "transition"),
  E("Ni", "Nickel",    28, 4, 10, "transition"),
  E("Cu", "Copper",    29, 4, 11, "transition"),
  E("Zn", "Zinc",      30, 4, 12, "transition"),
  E("Ga", "Gallium",   31, 4, 13, "post-transition"),
  E("Ge", "Germanium", 32, 4, 14, "metalloid"),
  E("As", "Arsenic",   33, 4, 15, "metalloid"),
  E("Se", "Selenium",  34, 4, 16, "nonmetal"),
  E("Br", "Bromine",   35, 4, 17, "halogen"),
  E("Kr", "Krypton",   36, 4, 18, "noble"),

  // Period 5
  E("Rb", "Rubidium",  37, 5, 1,  "alkali"),
  E("Sr", "Strontium", 38, 5, 2,  "alkaline"),
  E("Y",  "Yttrium",   39, 5, 3,  "transition"),
  E("Zr", "Zirconium", 40, 5, 4,  "transition"),
  E("Nb", "Niobium",   41, 5, 5,  "transition"),
  E("Mo", "Molybdenum",42, 5, 6,  "transition"),
  E("Tc", "Technetium",43, 5, 7,  "transition"),
  E("Ru", "Ruthenium", 44, 5, 8,  "transition"),
  E("Rh", "Rhodium",   45, 5, 9,  "transition"),
  E("Pd", "Palladium", 46, 5, 10, "transition"),
  E("Ag", "Silver",    47, 5, 11, "transition"),
  E("Cd", "Cadmium",   48, 5, 12, "transition"),
  E("In", "Indium",    49, 5, 13, "post-transition"),
  E("Sn", "Tin",       50, 5, 14, "post-transition"),
  E("Sb", "Antimony",  51, 5, 15, "metalloid"),
  E("Te", "Tellurium", 52, 5, 16, "metalloid"),
  E("I",  "Iodine",    53, 5, 17, "halogen"),
  E("Xe", "Xenon",     54, 5, 18, "noble"),

  // Period 6
  E("Cs", "Caesium",   55, 6, 1,  "alkali"),
  E("Ba", "Barium",    56, 6, 2,  "alkaline"),
  // La-Lu shown in row 8 (lanthanide strip)
  E("Hf", "Hafnium",   72, 6, 4,  "transition"),
  E("Ta", "Tantalum",  73, 6, 5,  "transition"),
  E("W",  "Tungsten",  74, 6, 6,  "transition"),
  E("Re", "Rhenium",   75, 6, 7,  "transition"),
  E("Os", "Osmium",    76, 6, 8,  "transition"),
  E("Ir", "Iridium",   77, 6, 9,  "transition"),
  E("Pt", "Platinum",  78, 6, 10, "transition"),
  E("Au", "Gold",      79, 6, 11, "transition"),
  E("Hg", "Mercury",   80, 6, 12, "transition"),
  E("Tl", "Thallium",  81, 6, 13, "post-transition"),
  E("Pb", "Lead",      82, 6, 14, "post-transition"),
  E("Bi", "Bismuth",   83, 6, 15, "post-transition"),
  E("Po", "Polonium",  84, 6, 16, "metalloid"),
  E("At", "Astatine",  85, 6, 17, "halogen"),
  E("Rn", "Radon",     86, 6, 18, "noble"),

  // Period 7
  E("Fr", "Francium",  87, 7, 1,  "alkali"),
  E("Ra", "Radium",    88, 7, 2,  "alkaline"),
  // Ac-Lr in row 9 (actinide strip)
  E("Rf", "Rutherfordium", 104, 7, 4,  "transition"),
  E("Db", "Dubnium",       105, 7, 5,  "transition"),
  E("Sg", "Seaborgium",    106, 7, 6,  "transition"),
  E("Bh", "Bohrium",       107, 7, 7,  "transition"),
  E("Hs", "Hassium",       108, 7, 8,  "transition"),
  E("Mt", "Meitnerium",    109, 7, 9,  "transition"),
  E("Ds", "Darmstadtium",  110, 7, 10, "transition"),
  E("Rg", "Roentgenium",   111, 7, 11, "transition"),
  E("Cn", "Copernicium",   112, 7, 12, "transition"),
  E("Nh", "Nihonium",      113, 7, 13, "post-transition"),
  E("Fl", "Flerovium",     114, 7, 14, "post-transition"),
  E("Mc", "Moscovium",     115, 7, 15, "post-transition"),
  E("Lv", "Livermorium",   116, 7, 16, "post-transition"),
  E("Ts", "Tennessine",    117, 7, 17, "halogen"),
  E("Og", "Oganesson",     118, 7, 18, "noble"),

  // Lanthanide series (visual row 8, groups 3–17)
  E("La", "Lanthanum",  57, 8, 3,  "lanthanide"),
  E("Ce", "Cerium",     58, 8, 4,  "lanthanide"),
  E("Pr", "Praseodymium",59,8, 5,  "lanthanide"),
  E("Nd", "Neodymium",  60, 8, 6,  "lanthanide"),
  E("Pm", "Promethium", 61, 8, 7,  "lanthanide"),
  E("Sm", "Samarium",   62, 8, 8,  "lanthanide"),
  E("Eu", "Europium",   63, 8, 9,  "lanthanide"),
  E("Gd", "Gadolinium", 64, 8, 10, "lanthanide"),
  E("Tb", "Terbium",    65, 8, 11, "lanthanide"),
  E("Dy", "Dysprosium", 66, 8, 12, "lanthanide"),
  E("Ho", "Holmium",    67, 8, 13, "lanthanide"),
  E("Er", "Erbium",     68, 8, 14, "lanthanide"),
  E("Tm", "Thulium",    69, 8, 15, "lanthanide"),
  E("Yb", "Ytterbium",  70, 8, 16, "lanthanide"),
  E("Lu", "Lutetium",   71, 8, 17, "lanthanide"),

  // Actinide series (visual row 9, groups 3–17)
  E("Ac", "Actinium",     89, 9, 3,  "actinide"),
  E("Th", "Thorium",      90, 9, 4,  "actinide"),
  E("Pa", "Protactinium", 91, 9, 5,  "actinide"),
  E("U",  "Uranium",      92, 9, 6,  "actinide"),
  E("Np", "Neptunium",    93, 9, 7,  "actinide"),
  E("Pu", "Plutonium",    94, 9, 8,  "actinide"),
  E("Am", "Americium",    95, 9, 9,  "actinide"),
  E("Cm", "Curium",       96, 9, 10, "actinide"),
  E("Bk", "Berkelium",    97, 9, 11, "actinide"),
  E("Cf", "Californium",  98, 9, 12, "actinide"),
  E("Es", "Einsteinium",  99, 9, 13, "actinide"),
  E("Fm", "Fermium",     100, 9, 14, "actinide"),
  E("Md", "Mendelevium", 101, 9, 15, "actinide"),
  E("No", "Nobelium",    102, 9, 16, "actinide"),
  E("Lr", "Lawrencium",  103, 9, 17, "actinide"),
];

/**
 * Elements that LeilMat disables in the picker:
 * - Noble gases (don't form alloys)
 * - Halogens (with the exception of trace dopants — for now disable)
 * - Highly radioactive / synthetic: anything Z > 92 plus Tc, Pm, Po, At, Fr, Ra
 */
const DISABLED_SET = new Set<string>([
  // Noble gases
  "He","Ne","Ar","Kr","Xe","Rn","Og",
  // Halogens (not commonly alloyed)
  "F","Cl","Br","I","At","Ts",
  // Highly radioactive / unstable
  "Tc","Pm","Po","Fr","Ra",
  "Np","Pu","Am","Cm","Bk","Cf","Es","Fm","Md","No","Lr",
  "Rf","Db","Sg","Bh","Hs","Mt","Ds","Rg","Cn","Nh","Fl","Mc","Lv",
]);

export function isElementDisabled(symbol: string): boolean {
  return DISABLED_SET.has(symbol);
}
