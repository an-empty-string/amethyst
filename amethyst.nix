{ config, lib, pkgs, ... }:

with lib; let
  cfg = config.services.amethyst;
in
{
  options = {
    services.amethyst = {
      enable = mkEnableOption "Amethyst Gemini server";

      package = mkOption {
        default = pkgs.amethyst;
        type = types.package;
      };

      hosts = mkOption {
        default = null;
        type = types.nullOr types.str;
        example = literalExpression ''"gemini.yourdomain.com otherdomain.com"'';
        description = ''
          A space-separated lists of hosts this server will accept requests for.
          Requests for other hosts will be rejected.
        '';
      };

      sslCertificatePath = mkOption {
        default = "/var/lib/amethyst/cert.pem";
        type = types.str;
        description = "The path to the SSL certificate file";
      };

      sslPrivateKeyPath = mkOption {
        default = "/var/lib/amethyst/key.pem";
        type = types.str;
        description = "The path to the SSL private key file";
      };

      path = mkOption {
        type = types.attrsOf (types.submodule {
          options = {
            root = mkOption {
              type = types.path;
              description = "Serve from this directory";
            };

            autoindex = mkOption {
              default = false;
              type = types.bool;
              description = "Enable directory listing";
            };

            cgi = mkOption {
              default = false;
              type = types.bool;
              description = "Run files with executable bit set as CGI";
            };
          };
        });
      };
    };
  };
  config = mkIf cfg.enable {
    environment.etc."amethyst.conf" = let
      pathBlocks = (map (path: ''
        [${path.path}]
        root = ${path.root}
        autoindex = ${boolToString path.autoindex}
        cgi = ${boolToString path.cgi}
      '') (sortProperties (mapAttrsToList (p: c: c // { path = p; }) cfg.path)));
    in {
      text = ''
        [global]
        hosts = ${cfg.hosts}

        ssl_cert = ${cfg.sslCertificatePath}
        ssl_key = ${cfg.sslPrivateKeyPath}

        ${concatStringsSep "\n\n" pathBlocks}
      '';
    };

    systemd.services.amethyst = {
      description = "Amethyst Gemini server";
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = "yes";
        StateDirectory = "amethyst";
        ExecStart = "${cfg.package}/bin/amethyst /etc/amethyst.conf";
        ReadWritePaths = sort lessThan (
          mapAttrsToList (p: c: c.root) cfg.path
        );
      };
    };
  };
}
