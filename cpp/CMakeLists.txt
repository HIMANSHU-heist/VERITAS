cmake_minimum_required(VERSION 3.16)
project(veritas CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(OpenSSL REQUIRED)

add_executable(hello src/hello.cpp)
add_executable(risk_engine src/risk_engine.cpp)
target_link_libraries(risk_engine OpenSSL::Crypto)
