{ pkgs ? import <nixpkgs> {} }:

pkgs.stdenvNoCC.mkDerivation {
  pname = "tailwindcss";
  version = "4.3.3";

  src = pkgs.fetchurl {
    url = "https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-linux-x64";
    hash = "sha256-3GGzrGuMnKh0wMxMV7JAl5GmTFVAQEyl9TZzYLq8MTo=";
  };

  dontUnpack = true;

  installPhase = ''
    install -Dm755 "$src" "$out/bin/tailwindcss"
  '';
}
