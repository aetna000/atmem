FROM python:3.12.12-slim-bookworm
# Build-time public dependency installation only; runtime is offline/read-only.
RUN pip install --no-cache-dir enola-cli==0.4.26
COPY entrypoint.py /opt/atmem-extraction.py
ENV ENOLA_NO_UPDATE_CHECK=1 ENOLA_NO_PROMPTS=1 HOME=/job/home TMPDIR=/job/tmp
USER 65534:65534
WORKDIR /job
ENTRYPOINT ["python", "-I", "/opt/atmem-extraction.py"]
