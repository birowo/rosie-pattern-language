/*  -*- Mode: C/l; -*-                                                       */
/*                                                                           */
/*  librosie.h                                                               */
/*                                                                           */
/*  © Copyright IBM Corporation 2016.                                        */
/*  LICENSE: MIT License (https://opensource.org/licenses/mit-license.html)  */
/*  AUTHOR: Jamie A. Jennings                                                */

struct string {
     uint32_t len;
     char *ptr;
};

/* extern int bootstrap (lua_State *L, const char *rosie_home); */
extern void require (const char *name, int assign_name);
extern void initialize(const char *rosie_home);
extern int rosie_api(const char *name, ...);
extern int new_engine(struct string *eid_string);

/* !@# */
extern void l_message (const char *pname, const char *msg);
extern lua_State *get_L();


