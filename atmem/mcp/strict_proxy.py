"""Opt-in closed-root-argument MCP guard; upstream tool behavior is unchanged.

Unknown root parameters are rejected before execution unless a tool explicitly
advertises additionalProperties=true. Values are never rewritten or discarded.
This stricter host policy is not a claim about JSON Schema's default semantics.
Standard-library-only so it can be staged beside a native agent installation.
"""
from __future__ import annotations

import json
import subprocess
import sys


def argument_error(schema,arguments):
    if not isinstance(arguments,dict):return 'Tool arguments must be an object.'
    properties=schema.get('properties',{})
    if schema.get('additionalProperties') is not True and set(arguments)-set(properties):
        return 'Unexpected tool arguments. Use exactly the advertised tool schema; a tool with no parameters requires {}.'
    if set(schema.get('required',()))-set(arguments):return 'Required tool arguments are missing.'
    return None


def serve(command,stdin=sys.stdin,stdout=sys.stdout):
    child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                           stderr=sys.stderr,text=True,bufsize=1)
    schemas={}
    def emit(value):stdout.write(json.dumps(value,separators=(',',':'))+'\n');stdout.flush()
    try:
        for line in stdin:
            request=json.loads(line)
            method=request.get('method')
            if method=='tools/call':
                params=request.get('params') or {};name=params.get('name')
                schema=schemas.get(name)
                problem=('Describe the tool before invoking it.' if schema is None else
                         argument_error(schema,params.get('arguments',{})))
                if problem:
                    emit({'jsonrpc':'2.0','id':request.get('id'),'result':{
                        'content':[{'type':'text','text':problem}], 'isError':True}})
                    continue
            child.stdin.write(line);child.stdin.flush()
            if 'id' not in request:continue
            while True:
                returned=child.stdout.readline()
                if not returned:raise RuntimeError('upstream MCP server exited')
                response=json.loads(returned)
                if response.get('id')==request['id']:
                    if method=='tools/list':
                        for tool in response.get('result',{}).get('tools',[]):
                            schemas[tool['name']]=tool.get('inputSchema',{})
                    emit(response);break
                emit(response)
    finally:
        child.terminate()
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)


if __name__=='__main__':
    arguments=sys.argv[1:]
    if arguments[:1]==['--']:arguments=arguments[1:]
    if not arguments:raise SystemExit('usage: strict_proxy.py -- MCP_COMMAND [ARGS...]')
    serve(arguments)
