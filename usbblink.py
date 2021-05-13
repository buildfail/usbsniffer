#!/usr/bin/env python3

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform

from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.integration.export import get_csr_header
from litex.soc.interconnect import stream
from litex.soc.cores.uart import UARTWishboneBridge, RS232PHY
from litex.soc.cores.gpio import GPIOOut

from litedram.modules import MT41K256M16
from litedram.phy import a7ddrphy

from gateware.usb import USBCore
from gateware.etherbone import Etherbone
from gateware.ft601 import FT601Sync, phy_description
from gateware.ulpi import ULPIPHY, ULPICore
from gateware.dramfifo import LiteDRAMFIFO

from litescope import LiteScopeAnalyzer


_io = [
    ("clk100", 0, Pins("J19"), IOStandard("LVCMOS33")),

    ("rgb_led", 0,
        Subsignal("r", Pins("W2")),
        Subsignal("g", Pins("Y1")),
        Subsignal("b", Pins("W1")),
        IOStandard("LVCMOS33"),
    ),

    ("rgb_led", 1,
        Subsignal("r", Pins("AA1")),
        Subsignal("g", Pins("AB1")),
        Subsignal("b", Pins("Y2")),
        IOStandard("LVCMOS33"),
    ),

    ("serial", 0,
        Subsignal("tx", Pins("U21")), # FPGA_GPIO0
        Subsignal("rx", Pins("T21")), # FPGA_GPIO1
        IOStandard("LVCMOS33"),
    ),

    ("ddram", 0,
        Subsignal("a", Pins(
            "M2 M5 M3 M1 L6 P1 N3 N2",
            "M6 R1 L5 N5 N4 P2 P6"),
            IOStandard("SSTL15")),
        Subsignal("ba", Pins("L3 K6 L4"), IOStandard("SSTL15")),
        Subsignal("ras_n", Pins("J4"), IOStandard("SSTL15")),
        Subsignal("cas_n", Pins("K3"), IOStandard("SSTL15")),
        Subsignal("we_n", Pins("L1"), IOStandard("SSTL15")),
        Subsignal("dm", Pins("G3 F1"), IOStandard("SSTL15")),
        Subsignal("dq", Pins(
            "G2 H4 H5 J1 K1 H3 H2 J5",
            "E3 B2 F3 D2 C2 A1 E2 B1"),
            IOStandard("SSTL15"),
            Misc("IN_TERM=UNTUNED_SPLIT_50")),
        Subsignal("dqs_p", Pins("K2 E1"), IOStandard("DIFF_SSTL15")),
        Subsignal("dqs_n", Pins("J2 D1"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_p", Pins("P5"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_n", Pins("P4"), IOStandard("DIFF_SSTL15")),
        Subsignal("cke", Pins("J6"), IOStandard("SSTL15")),
        Subsignal("odt", Pins("K4"), IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("G1"), IOStandard("SSTL15")),
        Misc("SLEW=FAST"),
    ),

    ("usb_fifo_clock", 0, Pins("D17"), IOStandard("LVCMOS33")),
    ("usb_fifo", 0,
        Subsignal("rst", Pins("K22")),
        Subsignal("data", Pins("A16 F14 A15 F13 A14 E14 A13 E13 B13 C15 C13 C14 B16 E17 B15 F16",
                               "A20 E18 B20 F18 D19 D21 E19 E21 A21 B21 A19 A18 F20 F19 B18 B17")),
        Subsignal("be", Pins("K16 L16 G20 H20")),
        Subsignal("rxf_n", Pins("M13")),
        Subsignal("txe_n", Pins("L13")),
        Subsignal("rd_n", Pins("K19")),
        Subsignal("wr_n", Pins("M15")),
        Subsignal("oe_n", Pins("L21")),
        Subsignal("siwua", Pins("M16")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),

    ("ulpi_sw", 0,
        Subsignal("s", Pins("Y8")),
        Subsignal("oe_n", Pins("Y9")),
        IOStandard("LVCMOS33"),
    ),

    ("ulpi_clock", 0, Pins("W19"), IOStandard("LVCMOS33")),
    ("ulpi", 0,
        Subsignal("data", Pins("AB18 AA18 AA19 AB20 AA20 AB21 AA21 AB22")),
        Subsignal("dir", Pins("W21")),
        Subsignal("stp", Pins("Y22")),
        Subsignal("nxt", Pins("W22")),
        Subsignal("rst", Pins("V20")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),

    ("ulpi_clock", 1, Pins("V4"), IOStandard("LVCMOS33")),
    ("ulpi", 1,
        Subsignal("data", Pins("AB2 AA3 AB3 Y4 AA4 AB5 AA5 AB6")),
        Subsignal("dir", Pins("AB7")),
        Subsignal("stp", Pins("AA6")),
        Subsignal("nxt", Pins("AB8")),
        Subsignal("rst", Pins("AA8")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),
]


class Platform(XilinxPlatform):
    default_clk_name = "clk100"
    default_clk_period = 10.0

    def __init__(self, toolchain="vivado", programmer="vivado"):
        XilinxPlatform.__init__(self, "xc7a35t-fgg484-1", _io,
                                toolchain=toolchain)
        self.toolchain.bitstream_commands = \
            ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]",
             "set_property BITSTREAM.CONFIG.CONFIGRATE 40 [current_design]"]
        self.toolchain.additional_commands = \
            ["write_cfgmem -force -format bin -interface spix4 -size 16 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.programmer = programmer
        self.add_platform_command("set_property INTERNAL_VREF 0.750 [get_iobanks 35]")


class _CRG(Module, AutoCSR):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.clock_domains.cd_ulpi0 = ClockDomain("ulpi0")
        self.clock_domains.cd_ulpi1 = ClockDomain("ulpi1")
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()

        self.clock_domains.cd_usb = ClockDomain()

        # usb clock domain (100MHz from usb)
        self.comb += self.cd_usb.clk.eq(platform.request("usb_fifo_clock"))
        self.comb += self.cd_usb.rst.eq(self.cd_sys.rst)

        # ulpi0 clock domain (60MHz from ulpi0)
        self.comb += self.cd_ulpi0.clk.eq(platform.request("ulpi_clock", 0))

        # ulpi1 clock domain (60MHz from ulpi1)
        self.comb += self.cd_ulpi1.clk.eq(platform.request("ulpi_clock", 1))

        clk100 = platform.request("clk100")

        # sys & ddr clock domains
        pll_locked = Signal()
        pll_fb = Signal()
        pll_sys = Signal()
        pll_sys4x = Signal()
        pll_sys4x_dqs = Signal()
        pll_clk200 = Signal()
        self.specials += [
            Instance("PLLE2_BASE",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                     # VCO @ 1600 MHz
                     p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=10.0,
                     p_CLKFBOUT_MULT=16, p_DIVCLK_DIVIDE=1,
                     i_CLKIN1=clk100, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

                     # 100 MHz
                     p_CLKOUT0_DIVIDE=16, p_CLKOUT0_PHASE=0.0,
                     o_CLKOUT0=pll_sys,

                     # 400 MHz
                     p_CLKOUT1_DIVIDE=4, p_CLKOUT1_PHASE=0.0,
                     o_CLKOUT1=pll_sys4x,

                     # 400 MHz dqs
                     p_CLKOUT2_DIVIDE=4, p_CLKOUT2_PHASE=90.0,
                     o_CLKOUT2=pll_sys4x_dqs,

                     # 200 MHz
                     p_CLKOUT3_DIVIDE=8, p_CLKOUT3_PHASE=0.0,
                     o_CLKOUT3=pll_clk200,
            ),
            Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
            Instance("BUFG", i_I=pll_sys4x, o_O=self.cd_sys4x.clk),
            Instance("BUFG", i_I=pll_sys4x_dqs, o_O=self.cd_sys4x_dqs.clk),
            Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll_locked),
            AsyncResetSynchronizer(self.cd_clk200, ~pll_locked)
        ]

        reset_counter = Signal(4, reset=15)
        ic_reset = Signal(reset=1)
        self.sync.clk200 += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=ClockSignal("clk200"), i_RST=ic_reset)


class BlinkerRGB(Module):
    def __init__(self, r, g, b, divbits=26):
        counter = Signal(divbits + 2)
        self.comb += [
            r.eq(counter[divbits-3]),
            g.eq(counter[divbits-2]),
            b.eq(counter[divbits-1]),
        ]
        self.sync += counter.eq(counter + 1)


class USBSnifferSoC(SoCCore):
    csr_peripherals = [
    ]

    def __init__(self, platform):
        clk_freq = int(100e6)
        SoCCore.__init__(self, platform, clk_freq,
            cpu_type=None,
            integrated_rom_size=0,
            integrated_sram_size=0x8000,
            with_uart=False,
            ident="USB2Sniffer Blinker",
            with_timer=False
        )
        self.submodules.crg = _CRG(platform)

        # usb phy
        usb_pads = platform.request("usb_fifo")
        self.submodules.usb_phy = FT601Sync(usb_pads, dw=32, timeout=1024)

        # loopback
        self.submodules.usb_loopback_fifo = stream.SyncFIFO(phy_description(32), 2048)
        self.comb += [
            self.usb_phy.source.connect(self.usb_loopback_fifo.sink),
            self.usb_loopback_fifo.source.connect(self.usb_phy.sink)
        ]

        # leds
        led0 = platform.request("rgb_led", 0)
        self.submodules.blinker0 = BlinkerRGB(led0.r, led0.g, led0.b)

        led1 = platform.request("rgb_led", 1)
        self.submodules.blinker1 = BlinkerRGB(led1.r, led1.g, led1.b)

        # timing constraints
        self.crg.cd_sys.clk.attr.add("keep")
        self.crg.cd_usb.clk.attr.add("keep")
        self.platform.add_period_constraint(self.crg.cd_sys.clk, 10.0)
        self.platform.add_period_constraint(self.crg.cd_usb.clk, 10.0)


def main():
    platform = Platform()
    soc = USBSnifferSoC(platform)
    builder = Builder(soc, output_dir="build", csr_csv="test/csr.csv")
    vns = builder.build()
    soc.do_exit(vns)


if __name__ == "__main__":
    main()
