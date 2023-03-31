#pragma once
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#ifndef INPORT_ANY
#define INPORT_ANY 0
#endif

#include <array>
#include <cstring>
#include <string>
#include <vector>


namespace udp {
  class SocketError : public std::exception {};
  class OpenError : public std::exception {};
  class CloseError : public std::exception {};
  class ShutdownError : public std::exception {};
  class BindError : public std::exception {};
  class ConnectError : public std::exception {};
  class SetSockOptError : public std::exception {};
  class GetSockNameError : public std::exception {};
  class SendError : public std::exception {};
  class RecvError : public std::exception {};
}

class UDPSocket
{
public:

  typedef struct sockaddr_in sockaddr_in_t;
  typedef struct sockaddr sockaddr_t;
  typedef std::vector<uint8_t> msg_t;

  struct IPv4;

  enum class Status : int
  {
    OK = 0,
    SocketError = -1,
    OpenError = SocketError,
    CloseError = -2,
    ShutdownError = -3,
    BindError = -4,
    ConnectError = BindError,
    SetSockOptError = -5,
    GetSockNameError = -6,
    SendError = -7,
    RecvError = -8,
    // AddressError = -66,
  };

  static constexpr uint16_t msg_buf_size = 10*1024;

private:

  int m_sock{ -1 };
  sockaddr_in_t m_self_addr{};
  socklen_t m_self_addr_len = sizeof(m_self_addr);
  sockaddr_in_t m_peer_addr{};
  socklen_t m_peer_addr_len = sizeof(m_peer_addr);

public:
  UDPSocket()
  {
    m_self_addr = IPv4{};
    m_peer_addr = IPv4{};
  }

  ~UDPSocket() { this->close(); }

  int open()
  {
    this->close();
    m_sock = (int)::socket(PF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (this->is_closed()) {
      throw udp::SocketError();
      // return (int)Status::SocketError;
    }
    return (int)Status::OK;
  }

  int close()
  {
    if (!this->is_closed()) {
      // int ret = ::shutdown(m_sock, SHUT_RDWR);
      // if (ret < 0) {
      //   // return (int)Status::ShutdownError;
      //   throw udp::ShutdownError();
      // }
      int ret = ::close(m_sock);
      if (ret < 0) {
        // return (int)Status::CloseError;
        throw udp::CloseError();
      }
      m_sock = -1;
    }
    return (int)Status::OK;
  }

  bool is_closed() const { return m_sock < 0; }

  int bind(const IPv4& ipaddr)
  {
    m_self_addr = ipaddr;
    m_self_addr_len = sizeof(m_self_addr);
    int opt = 1;
    int ret = ::setsockopt(m_sock, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));
    if (ret < 0) {
      // return (int)Status::SetSockOptError;
      throw udp::SetSockOptError();
    }
    ret = ::bind(m_sock, (sockaddr_t*)&m_self_addr, m_self_addr_len);
    if (ret < 0) {
      // return (int)Status::BindError;
      throw udp::BindError();
    }
    ret = ::getsockname(m_sock, (sockaddr_t*)&m_self_addr, &m_self_addr_len);
    if (ret < 0) {
      // return (int)Status::GetSocwkNameError;
      throw udp::GetSockNameError();
    }
    return (int)Status::OK;
  }

  int bind(uint16_t portno)
  {
    auto ipaddr = IPv4::Any(portno);
    return this->bind(ipaddr);
  }

  int bind_any() { return this->bind(INPORT_ANY); }

  int bind_any(uint16_t& portno)
  {
    int ret = this->bind(INPORT_ANY);
    if (ret < 0) {
      return ret;
    }
    portno = IPv4{ m_self_addr }.port;
    return (int)Status::OK;
  }

  int connect(const IPv4& ipaddr)
  {
    m_peer_addr = ipaddr;
    m_peer_addr_len = sizeof(m_peer_addr);
    int ret = ::connect(m_sock, (sockaddr_t*)&m_peer_addr, m_peer_addr_len);
    if (ret < 0) {
      // return (int)Status::ConnectError;
      throw udp::ConnectError();
    }
    return (int)Status::OK;
  }

  int connect(uint16_t portno)
  {
    auto ipaddr = IPv4::Loopback(portno);
    return this->connect(ipaddr);
  }

  IPv4 get_self_ip() const { return m_self_addr; }

  IPv4 get_peer_ip() const { return m_peer_addr; }

  template<typename T, typename = typename std::enable_if<sizeof(typename T::value_type) == sizeof(uint8_t)>::type>
  int send(const T& message, const IPv4& ipaddr) const
  {
    // // UPnP
    // std::string msg = "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: ssockp:discover\r\nST: ssockp:all\r\nMX: 1\r\n\r\n";
    sockaddr_in_t addr_in = ipaddr;
    socklen_t addr_in_len = sizeof(addr_in);
    int ret = ::sendto(m_sock, (const char*)message.data(), message.size(), 0, (sockaddr_t*)&addr_in, addr_in_len);
    if (ret < 0) {
      // return (int)Status::SendError;
      throw udp::SendError();
    }
    return ret;
  }

  template<typename T, typename = typename std::enable_if<sizeof(typename T::value_type) == sizeof(uint8_t)>::type>
  int recv(T& message, IPv4& ipaddr) const
  {
    sockaddr_in_t addr_in;
    socklen_t addr_in_len = sizeof(addr_in);
    typename T::value_type buffer[msg_buf_size];
    int ret = ::recvfrom(m_sock, (char*)buffer, sizeof(buffer), 0, (sockaddr_t*)&addr_in, &addr_in_len);
    if (ret < 0) {
      // return (int)Status::RecvError;
      throw udp::RecvError();
    }
    ipaddr = addr_in;
    message = { std::begin(buffer), std::begin(buffer) + ret };
    return ret;
  }

  int broadcast(int opt) const
  {
    int ret = ::setsockopt(m_sock, SOL_SOCKET, SO_BROADCAST, (const char*)&opt, sizeof(opt));
    if (ret < 0) {
      // return (int)Status::SetSockOptError;
      throw udp::SetSockOptError();
    }
    return (int)Status::OK;
  }

  int interrupt() const
  {
    uint16_t portno = IPv4{ m_self_addr }.port;
    auto ipaddr = IPv4::Loopback(portno);
    return this->send(msg_t{}, ipaddr);
  }

  struct IPv4
  {
    std::array<uint8_t, 4> octets{};
    uint16_t port{};

    IPv4() {}

    IPv4(const std::string& ipaddr, uint16_t portno)
    {
      int ret = ::inet_pton(AF_INET, ipaddr.c_str(), (uint32_t*)octets.data());
      if (ret > 0) {
        port = portno;
      } else {
        // throw std::runtime_error(Status::AddressError)
      }
    }

    IPv4(uint8_t a, uint8_t b, uint8_t c, uint8_t d, uint16_t portno)
    {
      octets[0] = a;
      octets[1] = b;
      octets[2] = c;
      octets[3] = d;
      port = portno;
    }

    IPv4(const sockaddr_in_t& addr_in)
    {
      *(uint32_t*)octets.data() = addr_in.sin_addr.s_addr;
      port = ntohs(addr_in.sin_port);
    }

    operator sockaddr_in_t() const
    {
      sockaddr_in_t addr_in;
      std::memset(&addr_in, 0, sizeof(addr_in));
      addr_in.sin_family = AF_INET;
      addr_in.sin_addr.s_addr = *(uint32_t*)octets.data();
      addr_in.sin_port = htons(port);
      return addr_in;
    }


  public:
    static IPv4 Any(uint16_t portno) { return IPv4{ INADDR_ANY, portno }; }
    static IPv4 Loopback(uint16_t portno) { return IPv4{ INADDR_LOOPBACK, portno }; }
    static IPv4 Broadcast(uint16_t portno) { return IPv4{ INADDR_BROADCAST, portno }; }

    const uint8_t& operator[](size_t octet) const { return octets[octet]; }
    uint8_t& operator[](size_t octet) { return octets[octet]; }

    bool operator==(const IPv4& other) const { return this->octets == other.octets && this->port == other.port; }

    bool operator!=(const IPv4& other) const { return !(*this == other); }

    std::string addr_string() const { return std::to_string(octets[0]) + '.' + std::to_string(octets[1]) + '.' + std::to_string(octets[2]) + '.' + std::to_string(octets[3]); }

    std::string port_string() const { return std::to_string(port); }

    std::string to_string() const { return this->addr_string() + ':' + this->port_string(); }

    operator std::string() const { return this->to_string(); }

  private:
    IPv4(uint32_t ipaddr, uint16_t portno)
    {
      *(uint32_t*)octets.data() = htonl(ipaddr);
      port = portno;
    }

  };
};

namespace std {
template<>
struct hash<UDPSocket::IPv4>
{
  typedef UDPSocket::IPv4 argument_type;
  typedef size_t result_type;
  result_type operator()(argument_type const& ipaddr) const noexcept
  {
    result_type const h1{ std::hash<uint32_t>{}(*(uint32_t*)ipaddr.octets.data()) };
    result_type const h2{ std::hash<uint16_t>{}(ipaddr.port) };
    return h1 ^ (h2 << 1);
  }
};
}