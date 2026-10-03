package core

import (
	"net/url"
	"regexp"
	"strings"
)

const (
	nativeCoverWebHostSuffix = "-novel.byteimg.com"
	nativeCoverWebStyle      = "~tplv-shrink:640:0.jpg"
	nativeCoverWebRoot       = "/novel-pic/"
)

var nativeCoverSignedHost = regexp.MustCompile(`^p([0-9])-reading-sign\.fqnovelpic\.com$`)

// nativeCoverWebAddress 把红果 App 接口下发的带签名 HEIC 模板地址换成同一张图的公共图床 JPEG 地址。
// 签名覆盖模板段，改写原地址后缀会被图床拒绝；部分平台引擎不包含 HEIF 解码器，因此必须换源。
func nativeCoverWebAddress(address string) string {
	parsed, err := url.Parse(address)
	if err != nil || parsed.User != nil {
		return ""
	}
	shard := nativeCoverSignedHost.FindStringSubmatch(parsed.Hostname())
	if shard == nil {
		return ""
	}
	index := strings.LastIndex(parsed.Path, "~tplv-")
	if index < 0 || !strings.HasPrefix(parsed.Path[:index], nativeCoverWebRoot) {
		return ""
	}
	parsed.Host = "p" + shard[1] + nativeCoverWebHostSuffix
	parsed.Path, parsed.RawPath, parsed.RawQuery, parsed.Fragment = parsed.Path[:index]+nativeCoverWebStyle, "", "", ""
	return parsed.String()
}
