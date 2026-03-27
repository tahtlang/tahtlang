class Tahtlang < Formula
  desc "A DSL for creating Reigns-style card games"
  homepage "https://github.com/tahtlang/tahtlang"
  version "0.5.0"
  license "MIT"

  on_macos do
    url "https://github.com/tahtlang/tahtlang/releases/download/v#{version}/tahtlang-macos-arm64"
    sha256 "PLACEHOLDER_MACOS_SHA256"

    def install
      bin.install "tahtlang-macos-arm64" => "tahtlang"
    end
  end

  on_linux do
    url "https://github.com/tahtlang/tahtlang/releases/download/v#{version}/tahtlang-linux-x86_64"
    sha256 "PLACEHOLDER_LINUX_SHA256"

    def install
      bin.install "tahtlang-linux-x86_64" => "tahtlang"
    end
  end

  test do
    assert_match "tahtlang", shell_output("#{bin}/tahtlang --help")
  end
end
