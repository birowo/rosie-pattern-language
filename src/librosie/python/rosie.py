# coding: utf-8
#  -*- Mode: Python; -*-                                              
# 
#  rosie.py     An interface to librosie from Python 2.7 and 3.6
# 
#  © Copyright IBM Corporation 2016, 2017, 2018.
#  LICENSE: MIT License (https://opensource.org/licenses/mit-license.html)
#  AUTHOR: Jamie A. Jennings

# Development environment:
#   Mac OS X Sierra (10.12.6)
#   Python 2.7.10 (distributed with OS X)
#   Python 3.6.4 (installed via brew on OS X)
#   cffi-1.11.4

# TODO:
# - replace magic error code numbers with constants
# - suppress the stderr output (librosie writes some error messages to stderr)

from __future__ import unicode_literals

from cffi import FFI
import os
import json

ffi = FFI()

# See librosie.h
ffi.cdef("""

typedef uint8_t * byte_ptr;

typedef struct rosie_string {
     uint32_t len;
     byte_ptr ptr;
} str;

typedef struct rosie_matchresult {
     str data;
     int leftover;
     int abend;
     int ttotal;
     int tmatch;
} match;

str *rosie_string_ptr_from(byte_ptr msg, size_t len);
void rosie_free_string_ptr(str *s);
void rosie_free_string(str s);

void *rosie_new(str *errors);
void rosie_finalize(void *L);
int rosie_libpath(void *L, str *newpath);
int rosie_alloc_limit(void *L, int *newlimit, int *usage);
int rosie_config(void *L, str *retvals);
int rosie_compile(void *L, str *expression, int *pat, str *errors);
int rosie_free_rplx(void *L, int pat);
int rosie_match(void *L, int pat, int start, char *encoder, str *input, match *match);
int rosie_matchfile(void *L, int pat, char *encoder, int wholefileflag,
		    char *infilename, char *outfilename, char *errfilename,
		    int *cin, int *cout, int *cerr,
		    str *err);
int rosie_trace(void *L, int pat, int start, char *trace_style, str *input, int *matched, str *trace);
int rosie_load(void *L, int *ok, str *src, str *pkgname, str *errors);
int rosie_loadfile(void *e, int *ok, str *fn, str *pkgname, str *errors);
int rosie_import(void *e, int *ok, str *pkgname, str *as, str *actual_pkgname, str *messages);
int rosie_read_rcfile(void *e, str *filename, int *file_exists, str *options);
int rosie_execute_rcfile(void *e, str *filename, int *file_exists, int *no_errors);

void free(void *obj);

""")

lib = None                # single instance of dynamic library

# -----------------------------------------------------------------------------
# ffi utilities

def free_cstr_ptr(local_cstr_obj):
    lib.rosie_free_string(local_cstr_obj[0])

# Note: bstring will be gc'd at the end of new_cstr unless we return
# it AND it is bound to a variable by the caller.  This is ugly, but
# seems necessary for Python3.  There must be a better way to cope
# with the fact that Python3 has separate, incompatible types for
# unicode strings (str) and byte arrays (bytes).
def new_cstr(bstring=None):
    if bstring:
        obj = lib.rosie_string_ptr_from(bstring, len(bstring))
        return ffi.gc(obj, lib.free)
    elif bstring is None:
        obj = ffi.new("struct rosie_string *")
        return ffi.gc(obj, free_cstr_ptr)
    else:
        raise ValueError("Unsupported argument type: " + str(type(pystring)))

def read_cstr(cstr_ptr):
    if cstr_ptr.ptr == ffi.NULL:
        return None
    else:
        return bytes(ffi.buffer(cstr_ptr.ptr, cstr_ptr.len)[:])

# -----------------------------------------------------------------------------

class engine ():
    '''
    Create a Rosie pattern matching engine.  The first call to engine()
    will load librosie from one of the standard shared library
    directories for your system, or from a custom path provided as an
    argument.
    '''

    def __init__(self, librosie_directory=None):
        global lib
        ostype = os.uname()[0]
        if ostype=="Darwin":
            libname = "librosie.dylib"
        else:
            libname = "librosie.so"
        if not lib:
            if librosie_directory:
               libpath = os.path.join(librosie_directory, libname)
               if not os.path.isfile(libpath):
                   raise RuntimeError("Cannot find librosie at " + libpath)
            elif use_local_librosie:
                libpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), libname)
                if not os.path.isfile(libpath):
                    raise RuntimeError("Cannot find librosie at " + libpath)
            else:
                libpath = libname
            lib = ffi.dlopen(libpath, ffi.RTLD_LAZY | ffi.RTLD_GLOBAL)
        Cerrs = new_cstr()
        self.engine = lib.rosie_new(Cerrs)
        if self.engine == ffi.NULL:
            raise RuntimeError("librosie: " + str(read_cstr(Cerrs)))
        return

    def config(self):
        Cresp = new_cstr()
        ok = lib.rosie_config(self.engine, Cresp)
        if ok != 0:
            raise RuntimeError("config() failed (please report this as a bug)")
        resp = read_cstr(Cresp)
        return resp

    def compile(self, exp):
        Cerrs = new_cstr()
        Cexp = new_cstr(exp)
        pat = rplx(self)
        ok = lib.rosie_compile(self.engine, Cexp, pat.id, Cerrs)
        if ok != 0:
            raise RuntimeError("compile() failed (please report this as a bug)")
        if pat.id[0] == 0:
            pat = None
        return pat, read_cstr(Cerrs)

    def load(self, src):
        Cerrs = new_cstr()
        Csrc = new_cstr(src)
        Csuccess = ffi.new("int *")
        Cpkgname = new_cstr()
        ok = lib.rosie_load(self.engine, Csuccess, Csrc, Cpkgname, Cerrs)
        if ok != 0:
            raise RuntimeError("load() failed (please report this as a bug)")
        errs = read_cstr(Cerrs)
        pkgname = read_cstr(Cpkgname)
        return Csuccess[0], pkgname, errs

    def loadfile(self, fn):
        Cerrs = new_cstr()
        Cfn = new_cstr(fn)
        Csuccess = ffi.new("int *")
        Cpkgname = new_cstr()
        ok = lib.rosie_loadfile(self.engine, Csuccess, Cfn, Cpkgname, Cerrs)
        if ok != 0:
            raise RuntimeError("loadfile() failed (please report this as a bug)")
        errs = read_cstr(Cerrs)
        pkgname = read_cstr(Cpkgname)
        return Csuccess[0], pkgname, errs

    def import_pkg(self, pkgname, as_name=None):
        Cerrs = new_cstr()
        if as_name:
            Cas_name = new_cstr(as_name)
        else:
            Cas_name = ffi.NULL
        Cpkgname = new_cstr(pkgname)
        Cactual_pkgname = new_cstr()
        Csuccess = ffi.new("int *")
        ok = lib.rosie_import(self.engine, Csuccess, Cpkgname, Cas_name, Cactual_pkgname, Cerrs)
        if ok != 0:
            raise RuntimeError("import() failed (please report this as a bug)")
        actual_pkgname = read_cstr(Cactual_pkgname) #if Cactual_pkgname.ptr != ffi.NULL else None
        errs = read_cstr(Cerrs)
        return Csuccess[0], actual_pkgname, errs

    def match(self, pat, input, start, encoder):
        if pat.id[0] == 0:
            raise ValueError("invalid compiled pattern")
        Cmatch = ffi.new("struct rosie_matchresult *")
        Cinput = new_cstr(input)
        ok = lib.rosie_match(self.engine, pat.id[0], start, encoder, Cinput, Cmatch)
        if ok != 0:
            raise RuntimeError("match() failed (please report this as a bug)")
        left = Cmatch.leftover
        abend = Cmatch.abend
        ttotal = Cmatch.ttotal
        tmatch = Cmatch.tmatch
        if Cmatch.data.ptr == ffi.NULL:
            if Cmatch.data.len == 0:
                return None, left, abend, ttotal, tmatch
            elif Cmatch.data.len == 1:
                return True, left, abend, ttotal, tmatch
            elif Cmatch.data.len == 2:
                raise ValueError("invalid output encoder")
            elif Cmatch.data.len == 4:
                raise ValueError("invalid compiled pattern (already freed?)")
        data = read_cstr(Cmatch.data)
        return data, left, abend, ttotal, tmatch

    def trace(self, pat, input, start, style):
        if pat.id[0] == 0:
            raise ValueError("invalid compiled pattern")
        Cmatched = ffi.new("int *")
        Cinput = new_cstr(input)
        Ctrace = new_cstr()
        ok = lib.rosie_trace(self.engine, pat.id[0], start, style, Cinput, Cmatched, Ctrace)
        if ok != 0:
            raise RuntimeError("trace() failed (please report this as a bug)")
        if Ctrace.ptr == ffi.NULL:
            if Ctrace.len == 2:
                raise ValueError("invalid trace style")
            elif Ctrace.len == 1:
                raise ValueError("invalid compiled pattern (already freed?)")
        matched = False if Cmatched[0]==0 else True
        trace = read_cstr(Ctrace)
        return matched, trace

    def matchfile(self, pat, encoder,
                  infile=None,  # stdin
                  outfile=None, # stdout
                  errfile=None, # stderr
                  wholefile=False):
        if pat.id[0] == 0:
            raise ValueError("invalid compiled pattern")
        Ccin = ffi.new("int *")
        Ccout = ffi.new("int *")
        Ccerr = ffi.new("int *")
        wff = 1 if wholefile else 0
        Cerrmsg = new_cstr()
        ok = lib.rosie_matchfile(self.engine,
                                 pat.id[0],
                                 encoder,
                                 wff,
                                 infile or b"",
                                 outfile or b"",
                                 errfile or b"",
                                 Ccin, Ccout, Ccerr, Cerrmsg)
        if ok != 0:
            raise RuntimeError("matchfile() failed: " + str(read_cstr(Cerrmsg)))

        if Ccin[0] == -1:       # Error occurred
            if Ccout[0] == 2:
                raise ValueError("invalid encoder")
            elif Ccout[0] == 3:
                raise ValueError(str(read_cstr(Cerrmsg))) # file i/o error
            elif Ccout[0] == 4:
                raise ValueError("invalid compiled pattern (already freed?)")
            else:
                raise ValueError("unknown error caused matchfile to fail")
        return Ccin[0], Ccout[0], Ccerr[0]

    def read_rcfile(self, filename=None):
        Cfile_exists = ffi.new("int *")
        if filename is None:
            filename_arg = new_cstr()
        else:
            filename_arg = new_cstr(filename)
        options = new_cstr()
        ok = lib.rosie_read_rcfile(self.engine, filename_arg, Cfile_exists, options)
        if ok != 0:
            raise RuntimeError("read_rcfile() failed (please report this as a bug)")
        if Cfile_exists[0] == 0: return None # file did not exist
        options = read_cstr(options)
        if options: return json.loads(options)
        return False   # file existed, but some problems processing it

    def execute_rcfile(self, filename=None):
        Cfile_exists = ffi.new("int *")
        Cno_errors = ffi.new("int *")
        if filename is None:
            filename_arg = new_cstr()
        else:
            filename_arg = new_cstr(filename)
        ok = lib.rosie_execute_rcfile(self.engine, filename_arg, Cfile_exists, Cno_errors)
        if ok != 0:
            raise RuntimeError("execute_rcfile() failed (please report this as a bug)")
        if Cfile_exists[0] == 0: return None # file did not exist
        if Cno_errors[0] == 1: return True
        return False   # file existed, but some problems processing it

    def libpath(self, libpath=None):
        if libpath:
            libpath_arg = new_cstr(libpath)
        else:
            libpath_arg = new_cstr()
        ok = lib.rosie_libpath(self.engine, libpath_arg)
        if ok != 0:
            raise RuntimeError("libpath() failed (please report this as a bug)")
        return read_cstr(libpath_arg) if libpath is None else None

    def alloc_limit(self, newlimit=None):
        limit_arg = ffi.new("int *")
        usage_arg = ffi.new("int *")
        if newlimit is None:
            limit_arg[0] = -1   # query
        else:
            if (newlimit != 0) and (newlimit < 8192):
                raise ValueError("new allocation limit must be 8192 KB or higher (or zero for unlimited)")
            limit_arg = ffi.new("int *")
            limit_arg[0] = newlimit
        ok = lib.rosie_alloc_limit(self.engine, limit_arg, usage_arg)
        if ok != 0:
            raise RuntimeError("alloc_limit() failed (please report this as a bug)")
        return limit_arg[0], usage_arg[0]

    def __del__(self):
        if hasattr(self, 'engine') and (self.engine != ffi.NULL):
            e = self.engine
            self.engine = ffi.NULL
            lib.rosie_finalize(e)

# -----------------------------------------------------------------------------

class rplx(object):    
    def __init__(self, engine):
        self.id = ffi.new("int *")
        self.engine = engine
        
    def __del__(self):
        if self.id[0] and self.engine.engine:
            lib.rosie_free_rplx(self.engine.engine, self.id[0])

    def maybe_valid(self):
        return self.id[0] != 0

    def valid(self):
        return self.maybe_valid() and \
            self.engine.engine and \
            isinstance(self.engine, engine)

    
# -----------------------------------------------------------------------------

# When this file is installed as a python module using pip, it comes
# with its own librosie.so/dylib, and that should be the default.  The
# setup.py for rosie ensures that by adding a line below that sets
# use_local_librosie to True.
use_local_librosie = False




