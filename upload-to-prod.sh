cd ~/PycharmProjects/rayv-app

mv settings_per_server.py settings_per_server.keep
find . -name '*.py' -print0 | xargs -0 rm
find . -name '*.html' -print0 | xargs -0 rm
find . -name '*.htt' -print0 | xargs -0 rm
find . -name '*.css' -print0 | xargs -0 rm
find . -name '*.jpg' -print0 | xargs -0 rm
find . -name '*.js' -print0 | xargs -0 rm
find . -name '*.png' -print0 | xargs -0 rm

cp -rp ~/PycharmProjects/rayv-preprod/*.py .
cp ~/PycharmProjects/rayv-preprod/index.yaml .
cp -rp ~/PycharmProjects/rayv-preprod/static/* ./static
cp -r ~/PycharmProjects/rayv-preprod/templates/* ./templates
cp -rp ~/PycharmProjects/rayv-preprod/*.pem .
rm settings_per_server.py
mv settings_per_server.keep settings_per_server.py
