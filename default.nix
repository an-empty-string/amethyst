{ lib, python3 }:

python3.pkgs.buildPythonApplication {
  pname = "amethyst";
  version = "0.0.1";

  src = ./.;

  propagatedBuildInputs = [
    python3.pkgs.cryptography
  ];
}
