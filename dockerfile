FROM ubuntu
COPY . /files
RUN cd /files && bash /files/install.sh
CMD ["bash", "-c", "cd /files && ./venv/bin/python3 main.py --auto-start-libvirt"]
EXPOSE 8880