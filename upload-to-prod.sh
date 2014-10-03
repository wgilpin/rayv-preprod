cd ~/PycharmProjects/rayv-prod

find . -name '*.py' -print0 | xargs -0 rm
find . -name '*.html' -print0 | xargs -0 rm
find . -name '*.htt' -print0 | xargs -0 rm
find . -name '*.css' -print0 | xargs -0 rm
find . -name '*.jpg' -print0 | xargs -0 rm
find . -name '*.js' -print0 | xargs -0 rm
find . -name '*.png' -print0 | xargs -0 rm
rm book.manifest

cp -rp ~/PycharmProjects/rayv-preprod/*.py .
cp -rp ~/PycharmProjects/rayv-preprod/static/* ./static
cp -r ~/PycharmProjects/rayv-preprod/templates/*.html ./templates
cp -r ~/PycharmProjects/rayv-preprod/templates/*.htt ./templates
cp book.manifest .
