public enum LenderType {
  // comment
  Provident(3L, "Provident Funding"),
  QuickenLoans(19L, "Rocket Pro", true, true), // after
  Freedom(6567741112713216L, "Freedom Mortgage", TierType.freedomTiers), // after
  PennyMac(1L, "PennyMac"),
  PennyMacCorrespondent(2L, "PennyMac Correspondent", true),
  AAALendings(4L, "AAA Lendings");
  private final String name;
}
