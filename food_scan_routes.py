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

    def _maybe_save(result, kind="scan"):
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
        try:
            from food_diary import save_meal
            product = result.get("product") or {}
            rating = result.get("rating") or {}
            macros = result.get("macros") or _macros(product)
            save_meal(email, {
                "name": product.get("name") or "Food",
                "calories": macros.get("calories"),
                "protein": macros.get("protein"),
                "carbs": macros.get("carbs"),
                "fat": macros.get("fat"),
                "sugar": macros.get("sugar"),
                "fiber": macros.get("fiber"),
                "sodium": macros.get("sodium"),
                "score": rating.get("score"),
                "label": rating.get("label") or "",
                "notes": macros.get("notes") or "",
                "thumbnail": _thumb(result),
                "portion": macros.get("portion") or kind,
            })
        except Exception as exc:
            print("[FoodScan] diary save skipped:", exc)
        result["saved"] = True
        return result

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
            return jsonify(_maybe_save(result, kind="scan"))
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
                result = _maybe_save(result, kind="scan")
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not read that label: %s" % exc})

    def api_meal():
        b64, mime, err = _read_image()
        if err:
            return jsonify({"ok": False, "error": err})
        try:
            from meal_photo import analyze_plate_for_client
            result = analyze_plate_for_client(b64, mime=mime, scan_raw=_scan_raw() if _logged_in() else "")
            if result.get("ok"):
                result["confidence"] = "estimate"
                result["uncertainty"] = "Plate photos are rough educational estimates. Portion size is often uncertain. Not medical advice."
                result["guest"] = not _logged_in()
                result = _maybe_save(result, kind="meal")
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not read that plate: %s" % exc})

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

    def api_guides():
        try:
            from food_guides import lists_for_flags
            top, low = lists_for_flags(_flags() if _logged_in() else [], raw_text=_scan_raw() if _logged_in() else "")
            return jsonify({"ok": True, "top": top[:40], "low": low[:40], "guest": not _logged_in()})
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
        ("/api/food-scan/history", "api_food_history_public", api_history, ["GET"]),
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
                    html = html.replace("<nav>", '<nav><a href="/scan-food">Scan Food</a>', 1)
                elif 'class="logo"' in html:
                    html = html.replace(
                        'class="logo">Root Cause</a>',
                        'class="logo">Root Cause</a><nav><a href="/scan-food">Scan Food</a></nav>',
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
