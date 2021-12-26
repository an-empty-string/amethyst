{ lib, python3 }:

python3.pkgs.buildPythonPackage {
  pname = "amethyst_extensions";
  version = "0.0.1";

  src = ./.;

  doCheck = false;
}
