def apply_look(pipeline, image_bgr, beard=None, color=None, cut=None):
    """A whole barber's order on one photo, in the order a barber works:
    the beard first, then the dye (over the new beard too), then the
    haircut. A step that cannot be done (no hair to dye or cut on a bald
    head) is skipped and reported instead of failing the whole order."""
    result = image_bgr
    skipped = []
    if beard:
        bearded = pipeline.apply_beard(result, beard, 0.9)
        if bearded is None:
            raise ValueError("No face detected in the image")
        result = bearded
    if color:
        try:
            dyed = pipeline.apply_hair_dye(result, color, 0.85, beard=bool(beard), beard_style=beard or None)
        except ValueError:
            dyed = None
        if dyed is None:
            skipped.append("dye")
        else:
            result = dyed
    if cut:
        try:
            cut_image = pipeline.apply_haircut(result, cut, 0.9)
        except ValueError:
            cut_image = None
        if cut_image is None:
            skipped.append("cut")
        else:
            result = cut_image
    return result, skipped
