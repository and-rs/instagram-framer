{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = [ (import ./tailwind.nix { inherit pkgs; }) ];
}
