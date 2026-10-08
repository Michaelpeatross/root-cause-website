"""Public Food Scanner + nutrition log routes. Safe to register after app bootstrap."""


def register_food_scan_routes(app, db=None, Report=None):
    from flask import render_template, request, session, jsonify

    def _email():
        return (session.get("email") or session.get("user_email") or "").strip().lower()

    def _logged_in():
        return bool(session.get("user_id") or _email())

    def _scan_raw():
        raw = session.get("latest_scan_raw") or ""
        if raw or not (_logged_in() and Report is not None):
            return raw or ""
        email = _email()
        if not email:
            return ""
        try:
            q = Report.query.filter(
                (Report.user_email == email) | (Report.client_email == email)
            )
        except Exception:
            try:
                q = Report.query.filter_by(user_email=email)
            except Exception:
                return ""
        try:
            row = q.order_by(Report.id.desc()).first()
        except Exception:
            return ""
        if not row:
            return ""
        return (
            getattr(row, "raw_data", None)
            or getattr(row, "original_text", None)
            or getattr(row, "generated_report", None)
            or ""
        )[:80000]

    def _flags():
        try:
            from food_scanner import client_flags_from_scan
            return client_flags_from_scan(_scan_raw())
        except Exception:
            return []

    def _macros(product, extra=None):
        n = (product or {}).get("nutrients") or {}
        out = {
            "calories": n.get("energy_kcal"),
            "protein": n.get("protein"),
            "carbs": n.get("carbs") if n.get("carbs") is not None else n.get("carbohydrates"),
            "fat": n.get("fat"),
            "fiber": n.get("fiber"),
            "sugar": n.get("sugars") if n.get("sugars") is not None else n.get("sugar"),
            "sodium": n.get("sodium"),
        }
        if extra:
            for key, val in extra.items():
                if val is not None:
                    out[key] = val
        return out

    def _enrich_product(product):
        if not product:
            return product
        n = product.setdefault("nutrients", {})
        if n.get("carbs") is None:
            n["carbs"] = n.get("carbohydrates")
        if n.get("energy_kcal") is None:
            n["energy_kcal"] = n.get("calories")
        return product

    def _thumb(result):
        product = (result or {}).get("product") or {}
        url = (product.get("image") or "")[:240]
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return ""

    def _maybe_save(result, kind="scan", to_diary=False):
        if not result or not result.get("ok") or not _logged_in():
            return result
        email = _email()
        if not email:
            return result
        try:
            from food_scan_history import save_scan
            save_scan(email, result)
        except Exception as exc:
            print("[FoodScan] history save skipped:", exc)
        if to_diary:
            try:
                _save_result_meal(email, result, kind)
                result["saved"] = True
            except Exception as exc:
                print("[FoodScan] diary save skipped:", exc)
        else:
            result["saved"] = False
        return result

    def _save_result_meal(email, result, kind="scan"):
        from food_diary import save_meal
        product = (result or {}).get("product") or {}
        rating = (result or {}).get("rating") or {}
        macros = (result or {}).get("macros") or _macros(product)
        return save_meal(email, {
            "name": product.get("name") or result.get("name") or "Food",
            "calories": macros.get("calories") if macros.get("calories") is not None else result.get("calories"),
            "protein": macros.get("protein") if macros.get("protein") is not None else result.get("protein"),
            "carbs": macros.get("carbs") if macros.get("carbs") is not None else result.get("carbs"),
            "fat": macros.get("fat") if macros.get("fat") is not None else result.get("fat"),
            "sugar": macros.get("sugar") if macros.get("sugar") is not None else result.get("sugar"),
            "fiber": macros.get("fiber"),
            "sodium": macros.get("sodium"),
            "score": rating.get("score") if rating.get("score") is not None else result.get("score"),
            "label": rating.get("label") or result.get("label") or "",
            "notes": macros.get("notes") or "",
            "thumbnail": _thumb(result),
            "portion": macros.get("portion") or kind,
        })

    def scan_food_page():
        return render_template(
            "food_scanner.html",
            personal_flags=(_flags() if _logged_in() else []),
            logged_in=_logged_in(),
        )

    def nutrition_page():
        return render_template("nutrition.html", logged_in=_logged_in())

    def blog_index():
        return render_template("blog/index.html")

    def api_barcode():
        data = request.get_json(silent=True) or {}
        code = data.get("barcode") or request.form.get("barcode") or request.args.get("barcode") or ""
        try:
            from food_scanner import lookup_barcode, score_product
            product = lookup_barcode(code)
            if not product:
                return jsonify({
                    "ok": False,
                    "error": "No product in the grocery database for that barcode. Try Search name or Label photo. Store brands are often missing.",
                })
            product = _enrich_product(product)
            flags = _flags() if _logged_in() else []
            result = {
                "ok": True,
                "product": product,
                "rating": score_product(product, flags),
                "macros": _macros(product),
                "confidence": "database",
                "uncertainty": "Barcode data can be incomplete. Values are usually per 100 g. Educational wellness only — not medical advice.",
                "guest": not _logged_in(),
            }
            return jsonify(_maybe_save(result, kind="scan", to_diary=False))
        except Exception as exc:
            return jsonify({"ok": False, "error": "Lookup failed: %s" % exc})

    def api_search():
        data = request.get_json(silent=True) or {}
        query = data.get("q") or data.get("query") or request.args.get("q") or ""
        try:
            from food_scanner import search_product_name
            return jsonify({"ok": True, "items": search_product_name(query), "guest": not _logged_in()})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "items": []})

    def _read_image():
        data = request.get_json(silent=True) or {}
        b64 = data.get("image_b64") or ""
        mime = data.get("mime") or "image/jpeg"
        if not b64 and request.files.get("file"):
            import base64
            raw = request.files["file"].read()
            b64 = base64.b64encode(raw).decode("ascii")
            mime = request.files["file"].mimetype or mime
        b64 = "".join(str(b64).split())
        if "," in b64 and b64.lower().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        if len(b64) < 80:
            return None, mime, "Choose or capture a photo first."
        if len(b64) > 9000000:
            return None, mime, "That photo is too large. Use a smaller JPEG or PNG."
        return b64, mime, None

    def api_photo():
        b64, mime, err = _read_image()
        if err:
            return jsonify({"ok": False, "error": err})
        try:
            from food_scanner import scan_photo_for_client
            result = scan_photo_for_client(b64, mime=mime, scan_raw=_scan_raw() if _logged_in() else "")
            if result.get("ok"):
                result["product"] = _enrich_product(result.get("product"))
                result["macros"] = result.get("macros") or _macros(result.get("product"))
                result["confidence"] = "estimate"
                result["uncertainty"] = "Label-photo values are estimates from the image. Not a lab analysis. Educational wellness only — not medical advice."
                result["guest"] = not _logged_in()
                # Shown first; the user taps "Add to today's intake" to log it.
                result = _maybe_save(result, kind="label", to_diary=False)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not read that label: %s" % exc})

    def api_meal():
        b64, mime, err = _read_image()
        if err:
            return jsonify({"ok": False, "error": err})
        try:
            import hashlib
            from meal_photo import analyze_plate_for_client
            result = analyze_plate_for_client(b64, mime=mime, scan_raw=_scan_raw() if _logged_in() else "")
            if result.get("ok"):
                result["confidence"] = "estimate"
                result["uncertainty"] = "Photo estimates are rough educational guides. Portions are often uncertain. Not medical advice."
                result["guest"] = not _logged_in()
                # Same photo -> same key, so re-estimating it never logs a second meal.
                result["photo_key"] = hashlib.sha1(b64[:400000].encode("ascii", "ignore")).hexdigest()[:16]
                # Nothing is logged here. The editable item list is shown first and
                # only "Save meal" (/api/food-scan/meal/save) adds it to today's intake.
                result["saved"] = False
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not read that photo: %s" % exc})

    def api_meal_item():
        """Re-look up one item after a rename / replace (food table, then a text estimate)."""
        data = request.get_json(silent=True) or {}
        name = str(data.get("name") or "").strip()[:60]
        if len(name) < 2:
            return jsonify({"ok": False, "error": "Type a food name."})
        try:
            from meal_items import lookup_food, make_item
            raw = lookup_food(name, data.get("grams"))
            if not raw:
                from meal_photo import estimate_food_text
                raw = estimate_food_text(name, data.get("portion") or "")
                if raw:
                    raw["source"] = "estimate"
            if not raw:
                return jsonify({"ok": False, "error": "No nutrition found for that name. The old numbers were kept; you can type calories instead."})
            raw["name"] = name
            for key in ("id", "eaten", "share", "share_override", "size"):
                if key in data:
                    raw[key] = data[key]
            return jsonify({"ok": True, "item": make_item(raw, _flags() if _logged_in() else [])})
        except Exception as exc:
            return jsonify({"ok": False, "error": "Lookup failed: %s" % exc})

    def api_food_names():
        q = request.args.get("q") or ""
        try:
            from meal_items import search_foods
            return jsonify({"ok": True, "items": search_foods(q)})
        except Exception as exc:
            return jsonify({"ok": False, "items": [], "error": str(exc)})

    def _meal_payload(data):
        from meal_items import normalize_items, compute_totals, compact_items, meal_name
        flags = _flags() if _logged_in() else []
        items = normalize_items(data.get("items") or [], flags)
        try:
            split = max(1, min(12, int(data.get("meal_split") or 1)))
        except (TypeError, ValueError):
            split = 1
        totals = compute_totals(items, split)
        name = str(data.get("name") or "").strip()[:80] or meal_name(items)
        from food_score_v2 import _band
        label = _band(totals["score"])[1] if totals.get("score") is not None else ""
        meal = {
            "name": name,
            "calories": totals["calories"], "protein": totals["protein"], "carbs": totals["carbs"],
            "fat": totals["fat"], "sugar": totals["sugar"], "fiber": totals["fiber"],
            "score": totals["score"], "label": label,
            "portion": "%d of %d items%s" % (totals["items_eaten"], len(items), (", split %d ways" % split) if split > 1 else ""),
            "items": compact_items(items, split), "meal_split": split, "source": "meal-photo",
            "save_id": str(data.get("save_id") or "")[:40],
            "photo_key": str(data.get("photo_key") or "")[:40],
        }
        return meal, items, totals

    def api_meal_save():
        data = request.get_json(silent=True) or {}
        if not data.get("items"):
            return jsonify({"ok": False, "error": "Add at least one food first."})
        try:
            meal, items, totals = _meal_payload(data)
            if totals["items_eaten"] == 0:
                return jsonify({"ok": False, "error": "Check at least one food you ate."})
            if not _logged_in():
                return jsonify({"ok": True, "saved": False, "guest": True, "meal": meal, "totals": totals})
            email = _email()
            from food_diary import save_meal, update_meal, daily_summary
            entry_id = str(data.get("entry_id") or "")
            if entry_id:
                fields = {k: meal[k] for k in ("name", "calories", "protein", "carbs", "fat", "sugar", "fiber", "score", "label", "portion", "items", "meal_split")}
                entry = update_meal(email, entry_id, fields)
                if not entry:
                    return jsonify({"ok": False, "error": "That meal is no longer in your log."})
                entry = dict(entry, replaced=True)
            else:
                entry = save_meal(email, meal)
                if not entry.get("replaced"):
                    try:
                        from food_scan_history import save_scan
                        save_scan(email, {"product": {"name": meal["name"], "code": ""},
                                          "rating": {"score": meal["score"], "label": meal["label"]},
                                          "macros": {k: meal[k] for k in ("calories", "protein", "carbs", "fat", "sugar", "fiber")}})
                    except Exception as exc:
                        print("[FoodScan] history save skipped:", exc)
            summary = daily_summary(email)
            return jsonify({"ok": True, "saved": True, "guest": False, "replaced": bool(entry.get("replaced")),
                            "meal": entry, "totals": totals, "today": summary.get("today") or {}})
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not save that meal: %s" % exc})

    def api_diary_delete():
        if not _logged_in():
            return jsonify({"ok": False, "error": "Log in to edit your log."}), 401
        data = request.get_json(silent=True) or {}
        try:
            from food_diary import delete_meal, daily_summary
            removed = delete_meal(_email(), data.get("id"))
            return jsonify({"ok": bool(removed), "error": "" if removed else "That meal is already gone.",
                            "today": daily_summary(_email()).get("today") or {}})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)})

    def api_diary_update():
        if not _logged_in():
            return jsonify({"ok": False, "error": "Log in to edit your log."}), 401
        data = request.get_json(silent=True) or {}
        fields = {}
        if "name" in data:
            fields["name"] = data.get("name")
        for key in ("calories", "protein", "carbs", "fat", "sugar", "fiber"):
            if key in data and data.get(key) not in (None, ""):
                try:
                    fields[key] = max(0.0, float(data.get(key)))
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": "%s must be a number." % key.capitalize()})
        if "scale" in data:
            # One-tap "I only had half" style edit for older entries without items.
            try:
                factor = max(0.05, min(10.0, float(data.get("scale"))))
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "Scale must be a number."})
            from food_diary import get_meal
            row = get_meal(_email(), data.get("id")) or {}
            for key in ("calories", "protein", "carbs", "fat", "sugar", "fiber"):
                if row.get(key) is not None:
                    try:
                        fields[key] = round(float(row[key]) * factor, 1)
                    except (TypeError, ValueError):
                        pass
        try:
            from food_diary import update_meal, daily_summary
            row = update_meal(_email(), data.get("id"), fields)
            if not row:
                return jsonify({"ok": False, "error": "That meal is no longer in your log."})
            return jsonify({"ok": True, "meal": row, "today": daily_summary(_email()).get("today") or {}})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)})

    def api_add_intake():
        if not _logged_in():
            return jsonify({"ok": False, "error": "Log in to add this to today's intake."}), 401
        data = request.get_json(silent=True) or {}
        email = _email()
        name = (data.get("name") or "").strip()
        code = "".join(ch for ch in str(data.get("code") or "") if ch.isdigit())
        calories = data.get("calories")
        try:
            if (calories is None or calories == "") and code:
                from food_scanner import lookup_barcode, score_product
                product = lookup_barcode(code)
                if not product:
                    return jsonify({"ok": False, "error": "That past scan has no saved numbers, and the barcode was not found."})
                product = _enrich_product(product)
                flags = _flags()
                rating = score_product(product, flags)
                macros = _macros(product)
                result = {"ok": True, "product": product, "rating": rating, "macros": macros}
            else:
                if not name:
                    return jsonify({"ok": False, "error": "That past item has no name to add."})
                result = {
                    "ok": True,
                    "product": {"name": name, "code": code},
                    "rating": {"score": data.get("score"), "label": data.get("label") or ""},
                    "macros": {
                        "calories": data.get("calories"),
                        "protein": data.get("protein"),
                        "carbs": data.get("carbs"),
                        "fat": data.get("fat"),
                        "sugar": data.get("sugar"),
                        "fiber": data.get("fiber"),
                        "sodium": data.get("sodium"),
                    },
                    "name": name,
                    "calories": data.get("calories"),
                    "protein": data.get("protein"),
                    "carbs": data.get("carbs"),
                    "fat": data.get("fat"),
                    "score": data.get("score"),
                    "label": data.get("label") or "",
                }
            meal = _save_result_meal(email, result, data.get("kind") or "intake")
            from food_diary import daily_summary
            summary = daily_summary(email)
            return jsonify({"ok": True, "meal": meal, "today": summary.get("today") or {}})
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not add that to today's intake: %s" % exc})

    def api_history():
        if not _logged_in():
            return jsonify({"ok": True, "items": [], "guest": True})
        try:
            from food_scan_history import sorted_history
            return jsonify({
                "ok": True,
                "items": sorted_history(_email(), sort=request.args.get("sort") or "date_desc"),
                "guest": False,
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "items": []})

    def api_diary():
        if not _logged_in():
            return jsonify({
                "ok": True,
                "guest": True,
                "today": {"meals": 0, "calories": 0, "protein": 0, "carbs": 0, "fat": 0},
                "days": [],
                "meals": [],
            })
        try:
            from food_diary import daily_summary
            data = daily_summary(_email())
            data["ok"] = True
            data["guest"] = False
            return jsonify(data)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "today": {}, "days": [], "meals": []})

    def api_delete_history():
        if not _logged_in():
            return jsonify({"ok": False, "error": "Log in to delete a scan."}), 401
        data = request.get_json(silent=True) or {}
        try:
            from food_scan_history import delete_scan
            removed = delete_scan(_email(), data.get("id"))
            return jsonify({"ok": bool(removed), "error": "" if removed else "That scan is already gone."})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)})

    def api_guides():
        try:
            from food_guides import lists_for_flags, perfect_score_foods
            top, low = lists_for_flags(_flags() if _logged_in() else [], raw_text=_scan_raw() if _logged_in() else "")
            return jsonify({
                "ok": True,
                "top": top[:40],
                "low": low[:40],
                "perfect": perfect_score_foods(100),
                "guest": not _logged_in(),
            })
        except Exception as exc:
            return jsonify({"ok": False, "top": [], "low": [], "error": str(exc)})

    routes = [
        ("/scan-food", "scan_food_public", scan_food_page, ["GET"]),
        ("/food-scanner", "food_scanner_public", scan_food_page, ["GET"]),
        ("/nutrition", "nutrition_public", nutrition_page, ["GET"]),
        ("/blog", "blog_index_public", blog_index, ["GET"]),
        ("/api/food-scan/barcode", "api_food_barcode_public", api_barcode, ["POST", "GET"]),
        ("/api/food-scan/search", "api_food_search_public", api_search, ["POST", "GET"]),
        ("/api/food-scan/photo", "api_food_photo_public", api_photo, ["POST"]),
        ("/api/food-scan/meal", "api_food_meal_public", api_meal, ["POST"]),
        ("/api/food-scan/meal/item", "api_food_meal_item_public", api_meal_item, ["POST"]),
        ("/api/food-scan/meal/save", "api_food_meal_save_public", api_meal_save, ["POST"]),
        ("/api/food-scan/foods", "api_food_names_public", api_food_names, ["GET"]),
        ("/api/food-scan/diary/delete", "api_food_diary_delete_public", api_diary_delete, ["POST"]),
        ("/api/food-scan/diary/update", "api_food_diary_update_public", api_diary_update, ["POST"]),
        ("/api/food-scan/history", "api_food_history_public", api_history, ["GET"]),
        ("/api/food-scan/history/delete", "api_food_history_delete_public", api_delete_history, ["POST"]),
        ("/api/food-scan/intake", "api_food_intake_public", api_add_intake, ["POST"]),
        ("/api/food-scan/diary", "api_food_diary_public", api_diary, ["GET"]),
        ("/api/food-scan/guides", "api_food_guides_public", api_guides, ["GET"]),
    ]
    existing_paths = {}
    for rule in app.url_map.iter_rules():
        existing_paths[rule.rule] = rule.endpoint
    for path, endpoint, view, methods in routes:
        if path in existing_paths:
            app.view_functions[existing_paths[path]] = view
            continue
        app.view_functions[endpoint] = view
        app.add_url_rule(path, endpoint, view, methods=methods)

    @app.after_request
    def _food_nav(response):
        try:
            if "text/html" not in (response.headers.get("Content-Type") or ""):
                return response
            html = response.get_data(as_text=True)
            if not html:
                return response
            if 'href="/scan-food"' not in html:
                if "<nav>" in html:
                    html = html.replace("<nav>", '<nav><a href="/scan-food">Food Scanner</a>', 1)
                elif 'class="logo"' in html:
                    html = html.replace(
                        'class="logo">Root Cause</a>',
                        'class="logo">Root Cause</a><nav><a href="/scan-food">Food Scanner</a></nav>',
                        1,
                    )
            if request.path == "/dashboard" and "My nutrition history" not in html:
                card = (
                    '<div class="card"><h2>My nutrition history</h2>'
                    "<p>Log meals from the Food Scanner. Educational estimates only.</p>"
                    '<p><a class="btn btn-primary" href="/scan-food">Scan Food</a> '
                    '<a class="btn btn-outline" href="/nutrition">Open nutrition log</a></p></div>'
                )
                html = html.replace(
                    "Your personalized bioenergetic portal</p>",
                    "Your personalized bioenergetic portal</p>" + card,
                    1,
                )
            response.set_data(html)
        except Exception as exc:
            print("[FoodScan] after_request skipped:", exc)
        return response

    print("[Root Cause] Registered public /scan-food + /food-scanner + nutrition APIs")
