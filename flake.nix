{
  description = "Amethyst, a Gemini server";
  outputs = { self, nixpkgs }: {
    nixosModules.default = (import ./module.nix);

    packages.x86_64-linux.default = let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
    in pkgs.python3Packages.buildPythonApplication {
      pname = "amethyst";
      version = "0.0.1";

      src = ./amethyst;
      propagatedBuildInputs = [
        pkgs.python3Packages.cryptography
        (pkgs.callPackage (import ./amethyst_extensions) {})
      ];
    };
  };
}
