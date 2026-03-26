class Tahtlang < Formula
  desc "A DSL for creating Reigns-style card games"
  homepage "https://github.com/tahtlang/tahtlang"
  version "0.1.0"
  license "MIT"

  on_macos do
    url "https://github.com/tahtlang/tahtlang/releases/download/v#{version}/tahtlang-macos-arm64"
    sha256 "4d6e16d3d229be7eb2cfe11f3ddb78bd0e6cfd097c900df626facc3a36895861"

    def install
      bin.install "tahtlang-macos-arm64" => "tahtlang"
    end
  end

  on_linux do
    url "https://github.com/tahtlang/tahtlang/releases/download/v#{version}/tahtlang-linux-x86_64"
    sha256 "c5fe35928f8a869aa3629ad049b65e77393f40ce855dbb113e075e3de164e89e"

    def install
      bin.install "tahtlang-linux-x86_64" => "tahtlang"
    end
  end

  test do
    assert_match "usage", shell_output("#{bin}/tahtlang --help")
  end
end
