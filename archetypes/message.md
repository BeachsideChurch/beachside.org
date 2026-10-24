{{- $baseName := .File.ContentBaseName -}}
{{- if or (eq $baseName "index") (eq $baseName "_index") -}}
{{- $baseName = path.Base .File.Dir -}}
{{- end -}}
---
title: "{{ replace $baseName "-" " " | title }}"
slug: "{{ replace $baseName "-" " " | title | urlize }}"
date: {{ .Date }}
lastmod: {{ .Date }}
speaker: ""
series: ""
part_number: ""
layout: ""
description: ""
image: "/images/messages/"
video_url: ""
audio_url: ""
guide_url: ""
draft: true
---