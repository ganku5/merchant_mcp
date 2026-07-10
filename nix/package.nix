{ lib, inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      workspace = inputs.uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ../.; };

      python = pkgs.python311;

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      pythonBase = pkgs.callPackage inputs.pyproject-nix.build.packages {
        inherit python;
      };

      pythonSet = pythonBase.overrideScope (
        lib.composeManyExtensions [
          inputs.pyproject-build-systems.overlays.wheel
          overlay
        ]
      );

      venv = pythonSet.mkVirtualEnv "merchant-mcp-env" workspace.deps.default;

      srcTree = lib.fileset.toSource {
        root = ../.;
        fileset = lib.fileset.unions [
          ../pyproject.toml
          ../src
          ../scripts
        ];
      };

      merchantMcp = pkgs.stdenv.mkDerivation {
        name = "merchant-mcp";
        src = srcTree;

        installPhase = ''
          mkdir -p $out/{bin,share/merchant-mcp}
          cp -r src $out/share/merchant-mcp/src
          cp -r scripts $out/share/merchant-mcp/scripts

          cat > $out/bin/merchant-mcp <<EOF
          #!${venv}/bin/python
          import os
          import sys
          sys.path.insert(0, "$out/share/merchant-mcp")
          port = int(os.environ.get("MCP_PORT", "8000"))
          host = os.environ.get("MCP_HOST", "0.0.0.0")
          sys.argv = [
            "uvicorn",
            "src.server.mcp_server:app",
            "--host", host,
            "--port", str(port),
          ] + sys.argv[1:]
          from uvicorn.main import main
          main()
          EOF
          chmod +x $out/bin/merchant-mcp
        '';
      };
    in
    {
      packages.default = merchantMcp;

      packages.dockerImage = pkgs.dockerTools.buildImage {
        name = "merchant-mcp";
        tag = "latest";
        created = "now";

        copyToRoot = pkgs.buildEnv {
          name = "merchant-mcp-root";
          paths = [ merchantMcp ];
        };

        config = {
          Cmd = [ "${merchantMcp}/bin/merchant-mcp" ];
          ExposedPorts = {
            "8000/tcp" = { };
          };
          WorkingDir = "/share/merchant-mcp";
          Env = [
            "PYTHONPATH=/share/merchant-mcp"
            "PYTHONUNBUFFERED=1"
          ];
        };
      };
    };
}
