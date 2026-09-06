"""Helpers for cortical parcel and other mesh-backed structure entries (Stage 3 completeness batches)."""
from lib import *

def mview(plane, mesh_id, label):
    """Imaging hint anchored on a manifest mesh centroid (resolved at build time)."""
    return {"plane": plane, "mni": {"meshId": mesh_id}, "label": label}

def cortex(id, name, lobe, summary, location, function, arteries, views, normal, paths, lesion, exam, pearls, cites, *,
           territories=(), synonyms=(), pathways=(), syndromes=(), afferents=(), efferents=(), pitfalls=(), tags=(), parent=None,
           subdivisions=(), latin=None, system="cerebrum", subsystem=None, mesh_ids=None, level=None):
    par = None if parent is False else (parent or f"lobe-{lobe}")
    return structure(id, name, system, summary, location, function, list(arteries), img(list(views), normal, list(paths)), list(lesion), list(exam), list(pearls), list(cites),
                     synonyms=synonyms, latin=latin, subsystem=subsystem or f"lobe-{lobe}", parent=par,
                     meshIds=mesh_ids if mesh_ids is not None else [id + "-l", id + "-r"], territories=territories, pathways=pathways, syndromes=syndromes,
                     afferents=afferents, efferents=efferents, pitfalls=pitfalls, tags=tags, subdivisions=subdivisions, level=level)

def LR(id):
    return [id + "-l", id + "-r"]
