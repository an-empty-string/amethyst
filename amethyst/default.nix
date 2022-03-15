{ lib
, pkgs
, python3
, extensionPackages ? [
  (pkgs.callPackage (import ../amethyst_extensions) {})
]}:

python3.pkgs.buildPythonApplication {
  pname = "amethyst";
  version = "0.0.1";

  src = ./.;

  propagatedBuildInputs = [
    python3.pkgs.cryptography
  ] ++ extensionPackages;
}
