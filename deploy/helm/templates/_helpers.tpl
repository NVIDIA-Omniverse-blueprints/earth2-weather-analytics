{{- define "earth2.selectors" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "earth2.labels" }}
{{- include "earth2.selectors" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}

# TODO: Remove this eventually
{{- define "earth2.busybox.command" }}
command:
    - "sh"
    - "-c"
    - "until nc -zv $K8S_REDIS_HOST $K8S_REDIS_PORT; do echo execute waiting for redis $K8S_REDIS_HOST $K8S_REDIS_PORT; sleep 2; done"
{{- end }}

{{- define "earth2.image.prefix" -}}
{{- if .Values.ngcImageRegistryPath -}}
nvcr.io/{{ .Values.ngcImageRegistryPath }}/
{{- end -}}
{{- end -}}
