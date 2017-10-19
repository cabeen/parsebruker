#!/usr/bin/env python
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

"""  This tool is for parsing Bruker method files into several different (and
hopefully more useful) formats.  This includes JSON output and formatted output
based on a used-specified pattern. There are four components derived from each
method file: the header, the header attributes, the parameters, and the
parameter attributes.  The header and parameters are key value pairs, and the
attributes are additional data attached to some of the key value pairs. The
header evidently encodes information related to the session date and compute
environment, while the parameters encode how the details of the scanner
protocol.  The attributes seem rather free-form, but among the things they
sore, you can find the spatial resolution and diffusion gradient b-vectors and
b-values. """

import re
import json

from sys import argv
from sys import path
from sys import exit
from sys import stdin
from sys import stdout
from sys import stderr

from os import environ
from os import getcwd
from os import makedirs
from os import chmod
from os import chdir
from os import getenv
from os import wait
from os import remove
from os import rmdir
from os import pathsep
from os import walk

from os.path import join
from os.path import basename
from os.path import dirname
from os.path import exists
from os.path import abspath
from os.path import isfile
from os.path import isdir
from os.path import pardir
from os.path import expanduser

import subprocess
from subprocess import STDOUT
from subprocess import call
from subprocess import Popen 
from datetime import datetime
from ConfigParser import RawConfigParser
from inspect import getargspec
from random import randint
from time import time
from optparse import OptionParser
from shutil import rmtree
from shutil import move
from string import Template

class Logger:
  def __init__(self):
    self.verbose = True 

  def __init__(self, v):
    self.verbose = v

  def info(self, msg):
    if self.verbose:
      print "[msg] %s" % msg
  
  def warn(self, msg):
    if self.verbose:
      print "[warn] %s" % msg
  
  def error(self, msg):
    print "[error] %s" % msg
    exit()
  
  def assume(self, cond, msg):
    if not cond:
      error(msg)

class Method:
  def __init__(self, array=False):
    self.array = array

  def parse_elem(self, val):
    attr = ""

    # it looks like arrays are surrounded by parentheses
    if re.match("^\(.*\).*", val):
      val = re.sub('^\(', '', val) 
      tokens = val.split(")", 1)
      val = tokens[0]
      if len(tokens) > 1:
        attr = tokens[1]

      if "," not in val:
        return [val.strip()], attr.strip()
      else:
        return [v.strip() for v in val.split(",")], attr.strip()
  
    # and combo choices are in brackets
    if re.match("^\<.*\>.*", val):
      val = re.sub('^\<', '', val) 
      tokens = val.split(">", 1)
      val = tokens[0]
      if len(tokens) > 1:
        attr = tokens[1]
      return [val.strip()], attr.strip()

    # only a string literal
    tokens = val.split(" ", 1)
    val = tokens[0]
    if len(tokens) > 1:
      attr = tokens[1]

    return [val], attr
  
  def parse(self, body):
    header = {}
    param = {}
    header_attr = {}
    param_attr = {}
  
    for group in body.split("##"):
      block = group.replace("\n", " ")

      # this makes it hard to parse and doesn't seem useful
      # so let's remove this part of the attribute       
      junk = "$$ @vis" 
      if junk in block:
        block = block.split(junk)[0].strip()
      
      if "=" in block:
        key, val = block.split("=", 1)
        vals, attr = self.parse_elem(val)
  
        if not self.array: 
          vals = " ".join(vals)

        if key.startswith("$"):
          key = re.sub('^\$', '', key) 
          param[key] = vals
          if len(attr) > 0:
            param_attr[key] = attr
        else:
          header[key] = vals
          if len(attr) > 0:
            header_attr[key] = attr
  
    self.header = header
    self.param = param
    self.header_attr = header_attr
    self.param_attr = param_attr 
  
    return self

  def format(self, pattern):

    # first we process the param values
    pattern = pattern.replace("$$", "#")
    pattern = Template(pattern).safe_substitute(self.param)

    for match in re.findall("\${(\w+)\[([0-9]+)\]", pattern):
      name = match[0]
      index = int(match[1])
      value = self.param[name].split(" ")[index]
      pattern = pattern.replace("%s[%d]" % (name, index), "tmp") 
      pattern = Template(pattern).safe_substitute({"tmp": value})

    # next we process the param attribute values
    pattern = pattern.replace("#", "$") 
    pattern = Template(pattern).safe_substitute(self.param_attr)

    for match in re.findall("\${(\w+)\[([0-9]+)\]", pattern):
      name = match[0]
      index = int(match[1])
      value = self.param_attr[name].split(" ")[index]
      pattern = pattern.replace("%s[%d]" % (name, index), "tmp") 
      pattern = Template(pattern).safe_substitute({"tmp": value})

    pattern = pattern.replace("Bruker:", "") 

    return pattern

def main():
  args = argv[1:]

  parser = OptionParser(usage="parsebruker <input|stdin> [opts]", description=__doc__)

  parser.add_option("--verbose", action="store_true", \
    help="print status messages")
  parser.add_option("--array", action="store_true", \
    help="store array values by entry, e.g. value[0], ...")
  parser.add_option("--write-header", metavar="<fn>", \
    help="write the header to a json file")
  parser.add_option("--write-header-attr", metavar="<fn>", \
    help="write the header attributes to a json file")
  parser.add_option("--write-param", metavar="<fn>", \
    help="write the parameter values to a json file")
  parser.add_option("--write-param-attr", metavar="<fn>", \
    help="write the parameter attributes to a json file")
  parser.add_option("--print-header", action="store_true", \
    help="print the header to a json file")
  parser.add_option("--print-header-attr", action="store_true", \
    help="print the header attributes to a json file")
  parser.add_option("--print-param", action="store_true", \
    help="print the parameter values to a json file")
  parser.add_option("--print-param-attr", action="store_true", \
    help="print the parameter attributes to a json file")
  parser.add_option("--format", metavar="<pattern>", action="store", \
    help="print a string formatted with parameter values, e.g. ${param1}_${param2}_$${attr1}.txt")

  (opts, pos) = parser.parse_args()

  if len(args) == 0 or len(pos) > 1:
    parser.print_help()
    return

  logger = Logger(opts.verbose)
  logger.info("started")

  logger.info("reading input")
  
  body = None
  if len(pos) > 0:
    input_fn = pos[0]
    logger.assume(exists(input_fn), "input file not found: %s" % input_fn)
    logger.info("reading file: %s" % input_fn)
    body = open(input_fn, 'r').read()
  else:
    logger.info("reading standard input")
    body = stdin.read() 

  method = Method(array=opts.array).parse(body)

  logger.info("writing output")

  def dumpit(lookup, fn):
    info("writing output: %s" % fn)
    open(fn, 'w').write(json.dumps(lookup, indent=2, sort_keys=False) + "\n")

  def printit(lookup):
    print json.dumps(lookup, indent=2, sort_keys=True)

  if opts.write_header:
    dumpit(method.header, opts.write_header)

  if opts.write_header_attr:
    dumpit(method.header_attr, opts.write_header_attr)

  if opts.write_param:
    dumpit(method.param, opts.write_param)

  if opts.write_param_attr:
    dumpit(method.param_attr, opts.write_param_attr)

  if opts.print_header:
    printit(method.header)

  if opts.print_header_attr:
    printit(method.header_attr)

  if opts.print_param:
    printit(method.param)

  if opts.print_param_attr:
    printit(method.param_attr)

  if opts.format:
    print method.format(opts.format)

  logger.info("finished")

if __name__ == "__main__":
    main() 

################################################################################
# End of file
################################################################################
