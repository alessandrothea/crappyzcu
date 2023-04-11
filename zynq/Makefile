
CXXFLAGS = -g -O2 -Isrc -std=c++17
LFLAGS = 

# output binary for each of these (no headers)
BSRC = $(wildcard src/*.cxx)
BOBJ = $(addprefix build/,$(notdir $(BSRC:.cxx=.o)))
BDEP = $(BOBJ:.o=.d)

# component object for each src/*.cc
LSRC = $(filter-out $(BSRC),$(wildcard src/*.cc))
LOBJ = $(addprefix build/,$(notdir $(LSRC:.cc=.o)))
LDEP = $(LOBJ:.o=.d)

BINS = $(notdir $(basename $(BSRC)))

all: $(BINS)
		@echo Finished building

install-wib:
		install -d "$(DESTDIR)/bin/"
		install -m 0755 hermes_udp_srv "$(DESTDIR)/bin/"
		install -m 0755 init_scripts/S99hermes_udp_srv_wib.sh "/etc/rc5.d"


clean:
		@rm -rf build $(PBGENS)

# binaries depend on all component objects
$(BINS): %: build/%.o $(LOBJ) $(PGOBJS)
		$(CXX) $< $(LOBJ) $(LFLAGS) -o $@

$(BDEP): build/%.d: src/%.cxx $(PBGENS)
		@mkdir -p build
		@set -e; rm -f $@
		$(CXX) -M $(CXXFLAGS) -MT $(<:.cxx=.o) $< > $@
		@sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' -i $@


$(LDEP): build/%.d: src/%.cc src/%.h $(PBGENS)
		@mkdir -p build
		@set -e; rm -f $@
		$(CXX) -M $(CXXFLAGS) -MT $(<:.cc=.o) $< > $@
		@sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' -i $@

# these won't exist the first build
-include $(LDEP) $(BDEP)

$(BOBJ): build/%.o: build/%.d $(PBGENS)
		$(CXX) $(CXXFLAGS) -c $(addprefix src/,$(notdir $(<:.d=.cxx))) -o $@

$(LOBJ): build/%.o: build/%.d $(PBGENS)
		$(CXX) $(CXXFLAGS) -c $(addprefix src/,$(notdir $(<:.d=.cc))) -o $@