// VERITAS deterministic risk + compliance engine.
// Reads one JSON request per line on stdin, writes one JSON response per line.
#include <algorithm>
#include <cmath>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <openssl/evp.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
namespace fs = std::filesystem;

static std::string sha256_hex(const std::string& s) {
    unsigned char md[EVP_MAX_MD_SIZE];
    unsigned int len = 0;
    EVP_Digest(s.data(), s.size(), md, &len, EVP_sha256(), nullptr);
    std::ostringstream o;
    for (unsigned int i = 0; i < len; ++i)
        o << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(md[i]);
    return o.str();
}

struct Engine {
    json costs = json::object();
    json limits = json::object();
    double capital = 1000000.0, equity = 1000000.0, peak = 1000000.0, day_pnl = 0.0;
    bool killed = false;
    std::string kill_reason;
    std::deque<long long> order_ts;
    std::string prev_hash = std::string(64, '0');
    std::string audit_path = "audit/audit.jsonl";

    double L(const char* k, double d) const { return limits.value(k, d); }
    double C(const char* k, double d) const { return costs.value(k, d); }

    void trip(const std::string& why) {
        if (!killed) { killed = true; kill_reason = why; }
    }

    // Cost of one leg (buy or sell) in INR.
    double leg_cost(double v, bool buy) const {
        double brk = std::min(C("brokerage_pct", 0.0003) * v, C("brokerage_max_inr", 20.0));
        double exch = C("exchange_txn_pct", 0.0) * v;
        double sebi = C("sebi_pct", 0.0) * v;
        double gst = C("gst_pct", 0.18) * (brk + exch + sebi);
        double stt = buy ? 0.0 : C("stt_sell_pct", 0.0) * v;
        double stamp = buy ? C("stamp_buy_pct", 0.0) * v : 0.0;
        double slip = C("slippage_bps", 0.0) / 10000.0 * v;
        return brk + exch + sebi + gst + stt + stamp + slip;
    }

    std::string log_entry(const json& req, const json& resp) {
        json entry = {{"request", req}, {"response", resp}, {"prev_hash", prev_hash}};
        std::string h = sha256_hex(prev_hash + entry.dump());
        entry["hash"] = h;
        prev_hash = h;
        fs::path p(audit_path);
        if (p.has_parent_path()) fs::create_directories(p.parent_path());
        std::ofstream(audit_path, std::ios::app) << entry.dump() << "\n";
        return h;
    }

    json check_order(const json& req) {
        double price = req.value("price", 0.0);
        double qty = req.value("qty", 0.0);
        long long ts = req.value("ts_ms", 0LL);
        double edge = req.value("expected_edge_pct", 0.0);
        std::vector<std::string> failed;

        if (killed) failed.push_back("kill_switch");
        if (!req.value("data_valid", true)) failed.push_back("data_invalid");
        if (!req.value("conformal_singleton", true)) failed.push_back("conformal_ambiguous");
        if (req.value("disagreement", 0.0) > L("max_disagreement", 0.6))
            failed.push_back("agent_disagreement");
        if (req.value("redteam_severity", "LOW") == "HIGH") failed.push_back("redteam_veto");
        if (req.value("vix", 0.0) > L("vix_abstain", 25.0)) failed.push_back("vix_stress");

        // Position size clip
        bool clipped = false;
        double max_val = capital * L("max_position_pct", 2.0) / 100.0;
        if (price > 0.0 && price * qty > max_val) {
            qty = std::floor(max_val / price);
            clipped = true;
        }
        if (price <= 0.0 || qty < 1.0) failed.push_back("invalid_size");
        double value = price * qty;

        // Cost gate
        double rt = leg_cost(value, true) + leg_cost(value, false);
        double cost_pct = value > 0.0 ? rt / value * 100.0 : 0.0;
        double required = cost_pct * L("edge_cost_multiple", 1.0);
        if (edge <= required) failed.push_back("edge_below_cost");

        // Rate limit (attempts per rolling second). A breach trips the kill-switch.
        while (!order_ts.empty() && ts - order_ts.front() > 1000) order_ts.pop_front();
        if (static_cast<double>(order_ts.size()) >= L("max_orders_per_second", 5.0)) {
            failed.push_back("rate_limit");
            trip("rate_limit_breach");
        }
        order_ts.push_back(ts);

        json resp;
        resp["type"] = "check_order";
        resp["decision"] = failed.empty() ? "TRADE" : "ABSTAIN";
        resp["gate_failed"] = failed;
        resp["qty_approved"] = failed.empty() ? qty : 0.0;
        resp["position_clipped"] = clipped;
        resp["round_trip_cost_inr"] = std::round(rt * 100.0) / 100.0;
        resp["cost_pct"] = std::round(cost_pct * 10000.0) / 10000.0;
        resp["required_edge_pct"] = std::round(required * 10000.0) / 10000.0;
        resp["edge_pct"] = edge;
        resp["killed"] = killed;
        if (std::find(failed.begin(), failed.end(), "edge_below_cost") != failed.end()) {
            std::ostringstream o;
            o << "Would TRADE if expected edge > " << std::fixed << std::setprecision(3)
              << required << "% (was " << edge << "%)";
            resp["counterfactual"] = o.str();
        }
        return resp;
    }

    json handle(const json& req) {
        std::string type = req.value("type", "");
        json resp = {{"type", type}};

        if (type == "config") {
            costs = req.value("costs", json::object());
            limits = req.value("limits", json::object());
            audit_path = req.value("audit_path", audit_path);
            capital = L("starting_capital_inr", 1000000.0);
            equity = peak = capital;
            day_pnl = 0.0;
            killed = false;
            kill_reason.clear();
            order_ts.clear();
            resp["status"] = "configured";
        } else if (type == "check_order") {
            resp = check_order(req);
        } else if (type == "update_pnl") {
            double pnl = req.value("pnl_inr", 0.0);
            equity += pnl;
            day_pnl += pnl;
            peak = std::max(peak, equity);
            if (day_pnl <= -capital * L("daily_loss_limit_pct", 2.0) / 100.0) trip("daily_loss_limit");
            double dd = peak > 0 ? (peak - equity) / peak * 100.0 : 0.0;
            if (dd >= L("max_drawdown_pct", 8.0)) trip("max_drawdown");
            resp["equity"] = equity;
            resp["day_pnl"] = day_pnl;
            resp["drawdown_pct"] = std::round(dd * 100.0) / 100.0;
            resp["killed"] = killed;
            resp["kill_reason"] = kill_reason;
        } else if (type == "new_day") {
            day_pnl = 0.0;
            resp["status"] = "new_day";
        } else if (type == "kill") {
            trip("manual");
            resp["killed"] = killed;
            resp["kill_reason"] = kill_reason;
        } else if (type == "reset") {
            killed = false;
            kill_reason.clear();
            order_ts.clear();
            resp["killed"] = killed;
        } else if (type == "status") {
            resp["killed"] = killed;
            resp["kill_reason"] = kill_reason;
            resp["equity"] = equity;
            resp["day_pnl"] = day_pnl;
        } else {
            resp["error"] = "unknown_type";
        }

        resp["audit_hash"] = log_entry(req, resp);
        return resp;
    }
};

static int verify_audit(const std::string& path) {
    std::ifstream f(path);
    std::string line, prev(64, '0');
    int n = 0;
    while (std::getline(f, line)) {
        ++n;
        json j;
        try { j = json::parse(line); }
        catch (...) { std::cout << json{{"audit", "BROKEN"}, {"line", n}}.dump() << "\n"; return 1; }
        std::string h = j.value("hash", "");
        j.erase("hash");
        if (j.value("prev_hash", "") != prev || sha256_hex(prev + j.dump()) != h) {
            std::cout << json{{"audit", "BROKEN"}, {"line", n}}.dump() << "\n";
            return 1;
        }
        prev = h;
    }
    std::cout << json{{"audit", "OK"}, {"lines", n}}.dump() << "\n";
    return 0;
}

int main(int argc, char** argv) {
    if (argc >= 3 && std::string(argv[1]) == "--verify") return verify_audit(argv[2]);

    Engine eng;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        json out;
        try {
            out = eng.handle(json::parse(line));
        } catch (const std::exception& e) {
            out = {{"error", e.what()}};
        }
        std::cout << out.dump() << std::endl;   // flush each line
    }
    return 0;
}