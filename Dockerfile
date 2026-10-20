FROM python:3.12-slim
ARG WHEEL=dist/tofscope-0.2.0-py3-none-any.whl
COPY ${WHEEL} /tmp/tofscope-0.2.0-py3-none-any.whl
RUN pip install --no-cache-dir /tmp/tofscope-0.2.0-py3-none-any.whl && useradd --uid 10001 --create-home tofscope && mkdir /data /runtime /saved && chown tofscope /runtime /saved
USER 10001
EXPOSE 8765
ENV TOFSCOPE_DATA_ROOT=/data TOFSCOPE_RUNTIME_DIR=/runtime TOFSCOPE_OUTPUT_ROOT=/saved TMPDIR=/runtime
ENTRYPOINT ["tofscope", "serve", "--no-browser"]
CMD ["--mode", "proxy", "--host", "0.0.0.0"]
