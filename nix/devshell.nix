{ config, lib, ... }:
{
  perSystem =
    {
      config,
      pkgs,
      ...
    }:
    let
      python = pkgs.python311;
    in
    {
      treefmt = {
        projectRootFile = "flake.nix";
        programs.nixfmt.enable = true;
        programs.ruff-format.enable = true;
      };

      devShells.default = pkgs.mkShell {
        name = "merchant-mcp-devshell";
        inputsFrom = [ config.pre-commit.devShell ];
        packages = [
          python
          pkgs.uv
          pkgs.basedpyright
          pkgs.just
        ];
        env = {
          UV_PYTHON_DOWNLOADS = "never";
          UV_PYTHON = python.interpreter;
        }
        // lib.optionalAttrs pkgs.stdenv.isLinux {
          LD_LIBRARY_PATH = lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
        };
        shellHook = ''
          unset PYTHONPATH
          echo 1>&2 "🐍: $(python --version)"
        '';
      };
    };
}
