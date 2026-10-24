#include <iostream>
#include <nlohmann/json.hpp>

int main() {
    nlohmann::json j;
    j["project"] = "VERITAS";
    j["status"] = "cpp_ok";
    std::cout << j.dump() << std::endl;
    return 0;
}
