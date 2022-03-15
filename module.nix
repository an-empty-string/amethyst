{ config, lib, pkgs, ... }:

with lib; let
  cfg = config.services.amethyst;
in
{
  imports = [
  ];

  options = {
    services.amethyst = {
      enable = mkEnableOption "Amethyst Gemini server";

      openFirewall = mkOption {
        default = true;
        type = types.bool;
      };

      package = mkOption {
        default = pkgs.callPackage (import ./amethyst) {};
        type = types.package;
      };

      port = mkOption {
        type = types.int;
        example = literalExpression "1965";
        default = 1965;
        description = "The port Amethyst will listen on.";
      };

      hosts = mkOption {
        default = { };
        type = types.listOf (types.submodule {
          options = {
            name = mkOption {
              type = types.str;
              description = "Name of host described by this block";
              example = literalExpression ''"gemini.tris.fyi"'';
            };

            tls = mkOption {
              type = types.attrs;
              example = literalExpression ''
                {
                  auto = false;
                  cert_path = "/path/to/cert.pem";
                  key_path = "/path/to/key.pem";
                }
              '';

              default = {};
              description = "TLS options for the host";
            };

            paths = mkOption {
              type = types.attrs;
              example = literalExpression ''
                {
                  "/" = {
                    root = "/var/gemini";
                    autoindex = true;
                    cgi = false;
                  };
                }
              '';

              default = {
                "/" = {
                  root = "/var/gemini";
                  autoindex = true;
                  cgi = false;
                };
              };

              description = "Path configuration for the host";
            };
          };
        });
      };
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = (length cfg.hosts) > 0;
        message = "You must define at least one host to enable Amethyst.";
      }
    ];

    environment.etc."amethyst.conf".text = builtins.toJSON cfg;

    systemd.services.amethyst = {
      description = "Amethyst Gemini server";
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = "yes";
        StateDirectory = "amethyst";
        ExecStart = "${cfg.package}/bin/amethyst /etc/amethyst.conf";
        ReadWritePaths = sort lessThan (unique (
          filter isString (lists.flatten (
            map (h: (
              mapAttrsToList
                (p: pc: if hasAttr "root" pc then pc.root else null) h.paths
              )
            ) cfg.hosts
          ))
        ));
      };
    };

    networking.firewall.allowedTCPPorts = mkIf cfg.openFirewall [ cfg.port ];
  };
}
