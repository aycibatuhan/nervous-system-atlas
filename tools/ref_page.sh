#!/bin/sh
# Render a printed page to PNG for visual reading.  usage: tools/ref_page.sh <snell|berkowitz> <printedPage>
set -e
cd "$(dirname "$0")/.."
book=$1; printed=$2
case $book in
  snell) pdf="source/Snell’s Clinical Neuroanatomy, 8E.pdf"; off=28; dpi=200;;
  berkowitz) pdf="source/Clinical Neurology and Neuroanatomy, A Localization-Based Approach.pdf"; off=15; dpi=110;;
  *) echo "book must be snell|berkowitz"; exit 1;;
esac
pdfpage=$((printed + off))
out=reference/$book/pages/p$(printf %04d "$printed")
mkdir -p "reference/$book/pages"
[ -f "$out.png" ] || pdftocairo -png -r $dpi -f $pdfpage -l $pdfpage -singlefile "$pdf" "$out"
echo "$PWD/$out.png"
