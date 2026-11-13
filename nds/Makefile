# Route Pico — app do console (.nds). Correr a partir de nds/.
#
# Host (Fase 1, sem toolchain):
#   make host-sim
#   ./build/routepico_host --sd tests/fixtures/fake_sd
#
# Testes C (também corridos pelo pytest da raiz, tests/test_nds_host.py):
#   make test
#
# NDS (requer DEVKITPRO + libnds + libfat):
#   make nds

.PHONY: all clean test host-sim host-test nds stub-info

APP      := RoutePico
BUILD    := build
HOST_BIN := $(BUILD)/routepico_host

HOST_CFLAGS := -std=c11 -Wall -Wextra -Wpedantic -Iinclude -DR1_HOST_SIM
HOST_SRCS := \
	src/main.c \
	src/app/browser.c \
	src/fs/fs.c \
	src/util/path.c \
	src/util/protect.c \
	src/util/err.c \
	src/input/input_host.c \
	src/ui/ui_host.c \
	src/usb/usb.c \
	src/integrity/integrity.c

TEST_PATH_SRCS := src/util/path.c src/util/protect.c src/util/err.c \
	tests/host/test_path.c
TEST_FS_SRCS := src/util/path.c src/util/protect.c src/util/err.c src/fs/fs.c \
	tests/host/test_fs.c

all: host-sim

host-sim: $(HOST_BIN)

$(HOST_BIN): $(HOST_SRCS) include/route1/*.h
	@mkdir -p $(BUILD)
	$(CC) $(HOST_CFLAGS) -O2 -o $@ $(HOST_SRCS)

host-test: $(BUILD)/test_path $(BUILD)/test_fs
	$(BUILD)/test_path
	$(BUILD)/test_fs

$(BUILD)/test_path: $(TEST_PATH_SRCS)
	@mkdir -p $(BUILD)
	$(CC) $(HOST_CFLAGS) -o $@ $(TEST_PATH_SRCS)

$(BUILD)/test_fs: $(TEST_FS_SRCS) tests/fixtures/fake_sd/.keep
	@mkdir -p $(BUILD)
	$(CC) $(HOST_CFLAGS) -o $@ $(TEST_FS_SRCS)

test: host-test

clean:
	rm -rf $(BUILD)

stub-info:
	@echo "make host-sim | make test | make nds (com DEVKITPRO)"

# --- NDS --------------------------------------------------------------------
nds:
ifndef DEVKITPRO
	$(error DEVKITPRO não definido. Instala devkitPro e exporta DEVKITPRO.)
endif
	$(MAKE) -f Makefile.nds

tests/fixtures/fake_sd/.keep:
	@mkdir -p tests/fixtures/fake_sd/Games tests/fixtures/fake_sd/Apps \
		tests/fixtures/fake_sd/_pico
	@touch tests/fixtures/fake_sd/.keep \
		tests/fixtures/fake_sd/_picoboot.nds \
		tests/fixtures/fake_sd/Games/demo.txt \
		tests/fixtures/fake_sd/Apps/readme.txt \
		tests/fixtures/fake_sd/_pico/settings.json \
		tests/fixtures/fake_sd/scratch_to_delete.txt
