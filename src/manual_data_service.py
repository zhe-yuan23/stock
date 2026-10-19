"""Validated access to the manually maintained financial CSV files.

The service keeps the existing CSV format as the source of truth.  In local
development it writes to the repository.  In a serverless deployment it can
write the same file through the GitHub Contents API when the GitHub settings
are configured.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


STOCK_ID_RE = re.compile(r"^\d{4}$")
DATASET_SPECS: dict[str, dict[str, Any]] = {
    "monthly_eps": {
        "filename": "monthly_eps",
        "key": "date",
        "columns": ["date", "stock_id", "eps_mon", "eps_ytd"],
        "required": ["date", "eps_mon"],
    },
    "yearly_revenue": {
        "filename": "yearly_revenue",
        "key": "year",
        "columns": ["year", "stock_id", "revenue_yearly"],
        "required": ["year", "revenue_yearly"],
    },
    "dividend_history": {
        "filename": "dividend_history",
        "key": "year",
        "columns": ["year", "stock_id", "eps", "cash_div", "stock_div"],
        "required": ["year", "eps", "cash_div", "stock_div"],
    },
    "historical_valuation": {
        "filename": "historical_valuation",
        "key": "year",
        "columns": ["year", "stock_id", "lowest_pe", "highest_pe", "annual_yield_pct"],
        "required": ["year", "lowest_pe", "highest_pe", "annual_yield_pct"],
    },
}


class ManualDataError(ValueError):
    """An invalid manual-data request."""


class ManualDataStore:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.manual_dir = repo_root / "data" / "manual_data"
        self.github_token = os.getenv("GITHUB_TOKEN", "").strip()
        self.github_repository = os.getenv("GITHUB_REPOSITORY", "").strip()
        self.github_branch = os.getenv("GITHUB_BRANCH", "main").strip() or "main"
        self.github_api_url = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")

    @property
    def uses_github(self) -> bool:
        return bool(self.github_token and self.github_repository)

    @property
    def storage_name(self) -> str:
        return "github" if self.uses_github else "local"

    def validate_stock_id(self, stock_id: str) -> str:
        stock_id = str(stock_id).strip()
        if not STOCK_ID_RE.fullmatch(stock_id):
            raise ManualDataError("股票代號必須是 4 位數字")
        return stock_id

    def validate_dataset(self, dataset: str) -> dict[str, Any]:
        try:
            return DATASET_SPECS[dataset]
        except KeyError as exc:
            supported = ", ".join(DATASET_SPECS)
            raise ManualDataError(f"不支援的資料類型，請使用：{supported}") from exc

    def _relative_path(self, stock_id: str, dataset: str) -> str:
        spec = self.validate_dataset(dataset)
        return f"data/manual_data/{stock_id}/{stock_id}_{spec['filename']}.csv"

    def _local_path(self, stock_id: str, dataset: str) -> Path:
        return self.repo_root / self._relative_path(stock_id, dataset)

    @staticmethod
    def _number(value: Any, field: str, *, allow_zero: bool = True) -> float:
        if value is None or str(value).strip() == "":
            raise ManualDataError(f"{field} 不可為空")
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ManualDataError(f"{field} 必須是數字") from exc
        if not math.isfinite(result) or (not allow_zero and result <= 0):
            raise ManualDataError(f"{field} 必須是有效數字")
        return result

    @staticmethod
    def _year(value: Any) -> str:
        try:
            year = int(value)
        except (TypeError, ValueError) as exc:
            raise ManualDataError("年度必須是整數") from exc
        if year < 1900 or year > 2100:
            raise ManualDataError("年度必須介於 1900 到 2100")
        return str(year)

    def normalize_record(self, stock_id: str, dataset: str, payload: dict[str, Any]) -> dict[str, Any]:
        stock_id = self.validate_stock_id(stock_id)
        spec = self.validate_dataset(dataset)
        if not isinstance(payload, dict):
            raise ManualDataError("資料格式必須是 JSON 物件")

        missing = [field for field in spec["required"] if payload.get(field) in (None, "")]
        if missing:
            raise ManualDataError(f"缺少欄位：{', '.join(missing)}")

        if dataset == "monthly_eps":
            try:
                date = pd.to_datetime(str(payload["date"]), format="%Y-%m-%d")
            except (TypeError, ValueError) as exc:
                raise ManualDataError("日期格式必須是 YYYY-MM-DD") from exc
            record = {
                "date": date.strftime("%Y-%m-%d"),
                "stock_id": stock_id,
                "eps_mon": self._number(payload["eps_mon"], "當月 EPS"),
            }
        elif dataset == "yearly_revenue":
            record = {
                "year": self._year(payload["year"]),
                "stock_id": stock_id,
                "revenue_yearly": self._number(payload["revenue_yearly"], "全年營收"),
            }
        elif dataset == "dividend_history":
            record = {
                "year": self._year(payload["year"]),
                "stock_id": stock_id,
                "eps": self._number(payload["eps"], "全年 EPS"),
                "cash_div": self._number(payload["cash_div"], "現金股利"),
                "stock_div": self._number(payload["stock_div"], "股票股利"),
            }
        else:
            record = {
                "year": self._year(payload["year"]),
                "stock_id": stock_id,
                "lowest_pe": self._number(payload["lowest_pe"], "最低本益比"),
                "highest_pe": self._number(payload["highest_pe"], "最高本益比"),
                "annual_yield_pct": self._number(payload["annual_yield_pct"], "年殖利率"),
            }

        return record

    @staticmethod
    def _recalculate_eps_ytd(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["eps_mon"] = pd.to_numeric(df["eps_mon"], errors="coerce")
        df = df.dropna(subset=["date", "eps_mon"]).sort_values("date").copy()
        df["eps_ytd"] = df.groupby(df["date"].dt.year)["eps_mon"].cumsum()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        return df

    def _read_local(self, stock_id: str, dataset: str) -> tuple[pd.DataFrame, str | None]:
        path = self._local_path(stock_id, dataset)
        if not path.exists():
            return pd.DataFrame(columns=self.validate_dataset(dataset)["columns"]), None
        return pd.read_csv(path), None

    def _github_request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.uses_github:
            raise ManualDataError("尚未設定 GITHUB_TOKEN 與 GITHUB_REPOSITORY")
        encoded_path = urllib.parse.quote(path, safe="/")
        url = f"{self.github_api_url}/repos/{self.github_repository}/contents/{encoded_path}"
        request = urllib.request.Request(url, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {self.github_token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None:
            request.add_header("Content-Type", "application/json")
            request.data = json.dumps(body).encode("utf-8")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method == "GET":
                return None
            detail = exc.read().decode("utf-8", errors="replace")
            raise ManualDataError(f"GitHub API 失敗 ({exc.code}): {detail[:300]}") from exc
        except urllib.error.URLError as exc:
            raise ManualDataError(f"GitHub API 連線失敗：{exc.reason}") from exc

    def _read_github(self, stock_id: str, dataset: str) -> tuple[pd.DataFrame, str | None]:
        path = self._relative_path(stock_id, dataset)
        result = self._github_request("GET", path)
        if not result:
            return pd.DataFrame(columns=self.validate_dataset(dataset)["columns"]), None
        try:
            raw = base64.b64decode(result["content"])
            return pd.read_csv(io.BytesIO(raw)), result.get("sha")
        except (KeyError, ValueError) as exc:
            raise ManualDataError(f"GitHub 檔案格式錯誤：{path}") from exc

    def read_all(self, stock_id: str) -> dict[str, list[dict[str, Any]]]:
        stock_id = self.validate_stock_id(stock_id)
        result: dict[str, list[dict[str, Any]]] = {}
        for dataset, spec in DATASET_SPECS.items():
            if self.uses_github:
                df, _ = self._read_github(stock_id, dataset)
            else:
                df, _ = self._read_local(stock_id, dataset)
            if dataset == "monthly_eps":
                df = self._recalculate_eps_ytd(df)
            if not df.empty:
                df = df.reindex(columns=spec["columns"])
            safe_df = df.astype(object).where(pd.notna(df), None)
            result[dataset] = safe_df.to_dict(orient="records")
        return result

    def upsert(self, stock_id: str, dataset: str, payload: dict[str, Any]) -> dict[str, Any]:
        stock_id = self.validate_stock_id(stock_id)
        spec = self.validate_dataset(dataset)
        record = self.normalize_record(stock_id, dataset, payload)

        if self.uses_github:
            df, sha = self._read_github(stock_id, dataset)
        else:
            if os.getenv("VERCEL", "").lower() == "1":
                raise ManualDataError("Vercel 尚未設定 GitHub 儲存，拒絕寫入暫存檔案")
            df, sha = self._read_local(stock_id, dataset)

        if df.empty:
            df = pd.DataFrame(columns=spec["columns"])
        else:
            df = df.reindex(columns=spec["columns"])

        key = spec["key"]
        if key in df.columns:
            df = df[df[key].astype(str) != str(record[key])]
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)

        if dataset == "monthly_eps":
            df = self._recalculate_eps_ytd(df)
        else:
            df = df.sort_values(key).reset_index(drop=True)

        output = io.StringIO()
        df.reindex(columns=spec["columns"]).to_csv(output, index=False)
        csv_text = output.getvalue()
        relative_path = self._relative_path(stock_id, dataset)

        if self.uses_github:
            message = f"Update {relative_path}"
            body: dict[str, Any] = {
                "message": message,
                "content": base64.b64encode(csv_text.encode("utf-8-sig")).decode("ascii"),
                "branch": self.github_branch,
            }
            if sha:
                body["sha"] = sha
            self._github_request("PUT", relative_path, body)
        else:
            path = self._local_path(stock_id, dataset)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(csv_text, encoding="utf-8-sig")

        return {
            "stock_id": stock_id,
            "dataset": dataset,
            "key": record[key],
            "record": record,
            "storage": self.storage_name,
            "github_branch": self.github_branch if self.uses_github else None,
        }
