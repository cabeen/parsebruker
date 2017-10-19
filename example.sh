#! /bin/bash
################################################################################
# 
# Copyright (c) 2017 Ryan Cabeen
# 
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 
################################################################################
# 
# This is an example of a script for processing Bruker data from a single
# session.  You'll probably have different fields you want to query, since they
# are study specific, but this # can perhaps give you an idea of how to use the
# tool.
# 
################################################################################

input="${yourdata}/input"
output="${yourdata}/output"
output="${yourdata}/scripts"

parse="python ${scripts}/parsebruker.py"

mkdir -p ${output}

echo "started bruker preprocessing"
echo "  using input: ${input}"
echo "  using output: ${output}"
echo "  using scripts: ${scripts}"

cd ${input}

for m in $(find . -name method -type f); do
	d=$(dirname ${m})
	e=$(basename ${d})

	echo "    processing batch: ${e}"

	method=$(cat ${m} | ${parse} --format '${Method}')
	dim=$(cat ${m} | ${parse} --format '$${PVM_SpatResol}' | wc -w)
	name="${method} ${dim}D"

	# 3D and 2D volumes store the slice thickness in difference fields
	if [ ${dim} -eq "2" ]; then
		name="${name} thick$(cat ${m} | ${parse} --format '${PVM_SliceThick}')"
	fi

	if [ ${dim} -eq "3" ]; then
		name="${name} thick$(cat ${m} | ${parse} --format '$${PVM_SpatResol[2]}')"
	fi

	format=''

	if grep --quiet PVM_DwNDiffDir ${m}; then
			format=${format}' dwndir${PVM_DwNDiffDir}'
	fi

	if grep --quiet PVM_DwBvalEach ${m}; then
			format=${format}' dwbval$${PVM_DwBvalEach}'
	fi

	name="${name} $(cat ${m} | ${parse} --format "${format}")"
	name=$(echo ${name} | sed 's/ /_/g')
	
	outd=${output}/${s}/${method}/${name}
	if [ ! -e ${outd} ]; then
		mkdir -p ${outd} 
		echo E${e}: ${name} >> ${report}

		for v in $(find ${d} -name "*.nii.gz"); do
			# preserve the subdirectories, which separates scanner reconstructions 
			p=$(basename $(dirname $(dirname ${v})))
			mkdir -p ${outd}/${p}
			ln ${v} ${outd}/${p}/$(basename ${v})
		done

		# store these json representations in case they are useful
		cat ${m} | ${parse} --print-header > ${outd}/header.json
		cat ${m} | ${parse} --print-header-attr > ${outd}/header_attr.json
		cat ${m} | ${parse} --print-param > ${outd}/param.json
		cat ${m} | ${parse} --print-param-attr > ${outd}/param_attr.json
  fi
done

echo "finished preprocessing"
