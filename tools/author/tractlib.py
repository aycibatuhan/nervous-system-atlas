from corlib import *
def tract(id, name, sub, summary, course, function, arteries, views, normal, paths, lesion, exam, pearls, cites, **kw):
    kw.setdefault("territories", []); kw.setdefault("parent", "cerebral-white-matter")
    kw.setdefault("tags", ["white matter", "tractography"])
    return cortex(id, name, "x", summary, course, function, arteries, views, normal, paths, lesion, exam, pearls, cites, system="tracts", subsystem=sub, **kw)
def T(id): return [id + "-l", id + "-r"]
