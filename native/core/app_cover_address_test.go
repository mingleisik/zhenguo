package core

import (
	"net/url"
	"testing"
)

func TestNativeCoverWebAddressRewritesSignedHEICTemplate(t *testing.T) {
	cases := []struct {
		name    string
		address string
		want    string
	}{
		{
			name:    "superreso aifit template",
			address: "https://p3-reading-sign.fqnovelpic.com/novel-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-81nmtwyey9-superreso-aifit:400:0.heic?lk3s=64477e16&x-expires=1796170316&x-signature=esjJZXrxFMtRQiizZxF1TQ9kOAs%3D",
			want:    "https://p3-novel.byteimg.com/novel-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-shrink:640:0.jpg",
		},
		{
			name:    "shrink template keeps shard",
			address: "https://p9-reading-sign.fqnovelpic.com/novel-pic/025da9124fe97c96cf173ac9e1ae4e12~tplv-shrink:1200:0.heic?lk3s=64477e16&x-expires=1796170324&x-signature=abc",
			want:    "https://p9-novel.byteimg.com/novel-pic/025da9124fe97c96cf173ac9e1ae4e12~tplv-shrink:640:0.jpg",
		},
		{
			name:    "double rz template",
			address: "https://p3-reading-sign.fqnovelpic.com/novel-pic/4be2393bc2eab64cd19159712730d00c~tplv-snk2bdmkp8-superreso-double-rz:1200:0.heic?x-signature=zzz",
			want:    "https://p3-novel.byteimg.com/novel-pic/4be2393bc2eab64cd19159712730d00c~tplv-shrink:640:0.jpg",
		},
		{
			name:    "unsigned address stays",
			address: "https://p3-novel.byteimg.com/novel-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-shrink:640:0.jpg",
			want:    "",
		},
		{
			name:    "other host stays",
			address: "https://pic.example.test/novel-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-shrink:640:0.heic",
			want:    "",
		},
		{
			name:    "host without shard stays",
			address: "https://reading-sign.fqnovelpic.com/novel-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-shrink:640:0.heic",
			want:    "",
		},
		{
			name:    "two digit shard stays",
			address: "https://p33-reading-sign.fqnovelpic.com/novel-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-shrink:640:0.heic",
			want:    "",
		},
		{
			name:    "template without root stays",
			address: "https://p3-reading-sign.fqnovelpic.com/other-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-shrink:640:0.heic",
			want:    "",
		},
		{
			name:    "address without template stays",
			address: "https://p3-reading-sign.fqnovelpic.com/novel-pic/d830237ffbf7a76b2c21b732777f03cc.heic",
			want:    "",
		},
		{
			name:    "userinfo stays",
			address: "https://user:pw@p3-reading-sign.fqnovelpic.com/novel-pic/d830237ffbf7a76b2c21b732777f03cc~tplv-shrink:640:0.heic",
			want:    "",
		},
		{
			name:    "empty stays",
			address: "",
			want:    "",
		},
	}
	for _, item := range cases {
		if got := nativeCoverWebAddress(item.address); got != item.want {
			t.Errorf("%s: got %q want %q", item.name, got, item.want)
		}
	}
}

func TestNativeCoverWebAddressResultIsDownloadable(t *testing.T) {
	address := nativeCoverWebAddress("https://p9-reading-sign.fqnovelpic.com/novel-pic/025da9124fe97c96cf173ac9e1ae4e12~tplv-shrink:1200:0.heic?lk3s=64477e16&x-signature=abc")
	parsed, err := url.Parse(address)
	if err != nil || !validNativeCoverURL(parsed) {
		t.Fatalf("rewritten address is not a valid cover URL: %q", address)
	}
	if parsed.Hostname() != "p9-novel.byteimg.com" || parsed.RawQuery != "" {
		t.Fatalf("rewritten address kept signature or wrong host: %q", address)
	}
}
