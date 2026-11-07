{{- define "agent-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agent-platform.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "agent-platform.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agent-platform.labels" -}}
app.kubernetes.io/name: {{ include "agent-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "agent-platform.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create -}}
{{- default (include "agent-platform.fullname" .) .Values.global.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.global.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "agent-platform.image" -}}
{{- printf "%s:%s" (required "global.image.repository is required" .Values.global.image.repository) (required "global.image.tag is required" .Values.global.image.tag) -}}
{{- end -}}
