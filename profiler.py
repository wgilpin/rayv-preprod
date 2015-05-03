from datetime import datetime, timedelta
import logging
import pickle
from google.appengine.api import memcache
from auth_logic import BaseHandler

__author__ = 'Will'

PROFILER = False


#record = {"fn":"name",
#          "in":"time",
#          "total":"time",
#          "max",time
#          "count":"no"}


class profile_reset(BaseHandler):
    def get(self):
        profiled = memcache.get("profiled")
        if profiled:
            profiled = pickle.loads(profiled)
            for fn in profiled:
                memcache.delete("profile:"+fn)
            memcache.delete("profiled")
            self.response.out.write("Reset. <br><br><a href='/profile'>Profile</a>")
        else:
            self.response.out.write("Nothing to reset. <br><br><a href='/profile'>Profile</a>")


def timedelta_to_microsecs(td):
    return td.microseconds + (td.seconds + td.days * 86400) * 1000000


def profile_in(function):
    if PROFILER:
        sums = memcache.get("profile:"+function)
        if sums:
            sums = pickle.loads(sums)
        if not sums:
            sums = {"in": 0,
                    "total": 0,
                    "count": 0,
                    "max": 0}
        sums["in"] = datetime.now()
        memcache.set("profile:"+function, pickle.dumps(sums))
        profile_list = memcache.get("profiled")
        if profile_list:
            profile_list = pickle.loads(profile_list)
        else:
            profile_list = []
        if not function in profile_list:
            profile_list.append(function)
        memcache.set("profiled",pickle.dumps(profile_list))



def profile_out(function):
    if PROFILER:
        try:
            now = datetime.now()
            sums = memcache.get("profile:"+function)
            if sums:
                sums = pickle.loads(sums)
                y = sums["in"]
                length = timedelta_to_microsecs(now - y)
                sums["count"] += 1
                sums["total"] += length
                if length > sums["max"]:
                    sums["max"] = length
                memcache.set("profile:"+function, pickle.dumps(sums))
                logging.info("profiler")
            else:
                logging.error("Profiler Mismatch")
        except Exception:
            logging.error("Profiler error ", exc_info=True)


class Report(BaseHandler):
    def get(self):
        profiled = pickle.loads(memcache.get("profiled"))
        prof_data = []
        errors = []
        for fn in profiled:
            try:
                fn_data = pickle.loads(memcache.get("profile:"+fn))
                fn_data["name"] = fn
                fn_data["avg"] = fn_data["total"] / fn_data["count"]
                prof_data.append(fn_data)
            except:
                errors.append("Error with "+fn)
        return self.render_template("profile.html", {"prof_data": prof_data,
                                                     "errors": errors})




